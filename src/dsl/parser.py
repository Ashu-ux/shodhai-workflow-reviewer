"""
Parser for the Routing Condition DSL.
Parses missing value checks, numeric boundary comparisons, string equality,
time unit declarations, nested AND/OR, and 'unless' ordered exceptions.
Preserves unsupported or ambiguous constructs as UnsupportedNode.
"""

import re
import math
from typing import Optional, List, Tuple
from src.contracts.dsl_ast import (
    ASTNode,
    MissingValueCheck,
    NumericInterval,
    EqualityCheck,
    BoolOpNode,
    NotNode,
    UnsupportedNode,
)


TIME_UNIT_TO_MINUTES = {
    "m": 1.0,
    "min": 1.0,
    "mins": 1.0,
    "minute": 1.0,
    "minutes": 1.0,
    "h": 60.0,
    "hr": 60.0,
    "hrs": 60.0,
    "hour": 60.0,
    "hours": 60.0,
    "s": 1.0 / 60.0,
    "sec": 1.0 / 60.0,
    "secs": 1.0 / 60.0,
    "second": 1.0 / 60.0,
    "seconds": 1.0 / 60.0,
    "d": 1440.0,
    "day": 1440.0,
    "days": 1440.0,
}


class ConditionParser:
    """Deterministic parser and canonicalizer for routing policy conditions."""

    @classmethod
    def parse(cls, text: str) -> ASTNode:
        if not text or not text.strip():
            return UnsupportedNode(raw_text=text or "", reason="Empty condition")
        
        cleaned = text.strip()
        
        # Handle "unless" ordered exceptions: "X unless Y" -> "X and not (Y)"
        if " unless " in cleaned.lower():
            parts = re.split(r"\s+unless\s+", cleaned, flags=re.IGNORECASE, maxsplit=1)
            left_node = cls.parse(parts[0])
            right_node = cls.parse(parts[1])
            return BoolOpNode(op="AND", operands=[left_node, NotNode(operand=right_node)])
        
        # Handle top-level OR (outside parentheses)
        or_parts = cls._split_by_top_level_op(cleaned, "or")
        if len(or_parts) > 1:
            return BoolOpNode(op="OR", operands=[cls.parse(p) for p in or_parts])
            
        # Handle top-level AND (outside parentheses)
        and_parts = cls._split_by_top_level_op(cleaned, "and")
        if len(and_parts) > 1:
            return BoolOpNode(op="AND", operands=[cls.parse(p) for p in and_parts])
            
        # Strip outer parentheses if balanced
        if cleaned.startswith("(") and cleaned.endswith(")") and cls._is_enclosed_in_parentheses(cleaned):
            return cls.parse(cleaned[1:-1])
            
        # Handle NOT
        if cleaned.lower().startswith("not ") or cleaned.lower().startswith("not("):
            rest = cleaned[3:].strip()
            return NotNode(operand=cls.parse(rest))

        # Check atomic patterns
        return cls._parse_atomic(cleaned)

    @classmethod
    def _is_enclosed_in_parentheses(cls, text: str) -> bool:
        depth = 0
        for i, char in enumerate(text):
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0 and i < len(text) - 1:
                    return False
        return depth == 0

    @classmethod
    def _split_by_top_level_op(cls, text: str, op: str) -> List[str]:
        parts = []
        depth = 0
        current = []
        words = re.split(r"(\s+|\(|\))", text)
        
        i = 0
        tokens = [w for w in words if w]
        buf = ""
        for token in tokens:
            if token == "(":
                depth += 1
                buf += token
            elif token == ")":
                depth -= 1
                buf += token
            elif depth == 0 and token.lower() == op:
                parts.append(buf.strip())
                buf = ""
            else:
                buf += token
        if buf.strip():
            parts.append(buf.strip())
        return parts if len(parts) > 1 else [text]

    @classmethod
    def _parse_atomic(cls, expr: str) -> ASTNode:
        expr = expr.strip()
        # Normalize ticket.field -> field
        expr = re.sub(r"\bticket\.", "", expr)

        # 1. Missing value checks:
        # e.g. "missing category", "category is None", "category is null", "category == None"
        missing_match = re.match(
            r"^(?:missing\s+(\w+)|(\w+)\s+is\s+(?:None|null)|(\w+)\s*==\s*(?:None|null))$",
            expr,
            flags=re.IGNORECASE
        )
        if missing_match:
            field = missing_match.group(1) or missing_match.group(2) or missing_match.group(3)
            return MissingValueCheck(field_name=field, is_missing=True)

        not_missing_match = re.match(
            r"^(\w+)\s+is\s+not\s+(?:None|null)$",
            expr,
            flags=re.IGNORECASE
        )
        if not_missing_match:
            field = not_missing_match.group(1)
            return MissingValueCheck(field_name=field, is_missing=False)

        # 2. String / categorical equality:
        # e.g. urgency == 'urgent' or urgency != 'urgent'
        str_eq_match = re.match(
            r"^(\w+)\s*(==|!=)\s*['\"]([^'\"]*)['\"]$",
            expr
        )
        if str_eq_match:
            field, op, val = str_eq_match.groups()
            return EqualityCheck(field_name=field, op=op, expected_value=val)

        # Boolean literal equality: e.g. is_vip == True
        bool_eq_match = re.match(
            r"^(\w+)\s*(==|!=)\s*(True|False)$",
            expr,
            flags=re.IGNORECASE
        )
        if bool_eq_match:
            field, op, val_str = bool_eq_match.groups()
            val = val_str.lower() == "true"
            return EqualityCheck(field_name=field, op=op, expected_value=val)

        # 3. Numeric comparisons:
        # standard: field op threshold [unit]
        # e.g. wait_time >= 30 minutes, wait_time > 25m, wait_time < 10
        num_match = re.match(
            r"^(\w+)\s*(>=|<=|>|<|==|!=)\s*([0-9]+(?:\.[0-9]+)?)\s*([a-zA-Z]+)?$",
            expr
        )
        if num_match:
            field, op, val_str, unit = num_match.groups()
            val = float(val_str)
            return cls._build_interval(field, op, val, unit)

        # swapped operands: threshold [unit] op field
        # e.g. 30 <= wait_time (equivalent to wait_time >= 30)
        swapped_num_match = re.match(
            r"^([0-9]+(?:\.[0-9]+)?)\s*([a-zA-Z]+)?\s*(>=|<=|>|<|==|!=)\s*(\w+)$",
            expr
        )
        if swapped_num_match:
            val_str, unit, op, field = swapped_num_match.groups()
            val = float(val_str)
            # Invert comparison operator when flipping operands
            invert_ops = {">=": "<=", "<=": ">=", ">": "<", "<": ">", "==": "==", "!=": "!="}
            return cls._build_interval(field, invert_ops[op], val, unit)

        # Natural language short-hands:
        # e.g. "urgent ticket" -> urgency == 'urgent'
        if expr.lower() in ("urgent ticket", "ticket is urgent", "urgent"):
            return EqualityCheck(field_name="urgency", op="==", expected_value="urgent")
        if expr.lower() in ("vip ticket", "ticket is vip", "vip"):
            return EqualityCheck(field_name="is_vip", op="==", expected_value=True)

        # If none matched, mark as UnsupportedNode to preserve visibility
        return UnsupportedNode(
            raw_text=expr,
            reason="Ambiguous or unsupported syntax in condition clause"
        )

    @classmethod
    def _build_interval(cls, field: str, op: str, val: float, unit_str: Optional[str]) -> NumericInterval:
        canonical_val = val
        if unit_str and unit_str.lower() in TIME_UNIT_TO_MINUTES:
            factor = TIME_UNIT_TO_MINUTES[unit_str.lower()]
            canonical_val = val * factor

        if op == ">=":
            return NumericInterval(field_name=field, min_val=canonical_val, min_inclusive=True)
        elif op == ">":
            return NumericInterval(field_name=field, min_val=canonical_val, min_inclusive=False)
        elif op == "<=":
            return NumericInterval(field_name=field, max_val=canonical_val, max_inclusive=True)
        elif op == "<":
            return NumericInterval(field_name=field, max_val=canonical_val, max_inclusive=False)
        elif op == "==":
            return NumericInterval(
                field_name=field,
                min_val=canonical_val,
                min_inclusive=True,
                max_val=canonical_val,
                max_inclusive=True
            )
        else:  # !=
            # Not supported as a single continuous interval
            return UnsupportedNode(
                raw_text=f"{field} {op} {val} {unit_str or ''}".strip(),
                reason="Non-equality numeric interval requires disjunction"
            )
