"""
Domain AST Representation for Routing Conditions, Numeric Boundaries, and Time Units.
Enables exact equivalence checking, boundary comparison, and counterexample generation.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Union
import math


@dataclass
class ASTNode:
    """Base class for all condition AST nodes."""
    def evaluate(self, ticket: Dict[str, Any]) -> bool:
        raise NotImplementedError

    def to_canonical_str(self) -> str:
        raise NotImplementedError


@dataclass
class MissingValueCheck(ASTNode):
    field_name: str
    is_missing: bool = True

    def evaluate(self, ticket: Dict[str, Any]) -> bool:
        val = ticket.get(self.field_name)
        is_none = (val is None or val == "" or self.field_name not in ticket)
        return is_none if self.is_missing else not is_none

    def to_canonical_str(self) -> str:
        op = "is None" if self.is_missing else "is not None"
        return f"{self.field_name} {op}"


@dataclass
class NumericInterval(ASTNode):
    field_name: str
    min_val: float = -math.inf
    min_inclusive: bool = False
    max_val: float = math.inf
    max_inclusive: bool = False
    unit: str = "minutes"  # Canonical time unit

    def evaluate(self, ticket: Dict[str, Any]) -> bool:
        val = ticket.get(self.field_name)
        if val is None or not isinstance(val, (int, float)):
            return False
        
        # Check lower bound
        if self.min_val != -math.inf:
            if self.min_inclusive:
                if val < self.min_val - 1e-9:
                    return False
            else:
                if val <= self.min_val + 1e-9:
                    return False
                
        # Check upper bound
        if self.max_val != math.inf:
            if self.max_inclusive:
                if val > self.max_val + 1e-9:
                    return False
            else:
                if val >= self.max_val - 1e-9:
                    return False
                
        return True

    def equals(self, other: "NumericInterval", tol: float = 1e-5) -> bool:
        if not isinstance(other, NumericInterval):
            return False
        if self.field_name != other.field_name:
            return False
        
        # Check lower
        if abs(self.min_val - other.min_val) > tol and not (math.isinf(self.min_val) and math.isinf(other.min_val)):
            return False
        if not math.isinf(self.min_val) and self.min_inclusive != other.min_inclusive:
            return False
            
        # Check upper
        if abs(self.max_val - other.max_val) > tol and not (math.isinf(self.max_val) and math.isinf(other.max_val)):
            return False
        if not math.isinf(self.max_val) and self.max_inclusive != other.max_inclusive:
            return False
            
        return True

    def to_canonical_str(self) -> str:
        left_bracket = "[" if self.min_inclusive else "("
        right_bracket = "]" if self.max_inclusive else ")"
        min_str = "-inf" if math.isinf(self.min_val) else f"{self.min_val:g}"
        max_str = "inf" if math.isinf(self.max_val) else f"{self.max_val:g}"
        return f"{self.field_name} in {left_bracket}{min_str}, {max_str}{right_bracket} ({self.unit})"


@dataclass
class EqualityCheck(ASTNode):
    field_name: str
    op: str  # "==" or "!="
    expected_value: Any

    def evaluate(self, ticket: Dict[str, Any]) -> bool:
        val = ticket.get(self.field_name)
        if self.op == "==":
            return val == self.expected_value
        elif self.op == "!=":
            return val != self.expected_value
        return False

    def to_canonical_str(self) -> str:
        val_repr = repr(self.expected_value) if isinstance(self.expected_value, str) else str(self.expected_value)
        return f"{self.field_name} {self.op} {val_repr}"


@dataclass
class BoolOpNode(ASTNode):
    op: str  # "AND" or "OR"
    operands: List[ASTNode] = field(default_factory=list)

    def evaluate(self, ticket: Dict[str, Any]) -> bool:
        if not self.operands:
            return True if self.op == "AND" else False
        if self.op == "AND":
            return all(op.evaluate(ticket) for op in self.operands)
        elif self.op == "OR":
            return any(op.evaluate(ticket) for op in self.operands)
        return False

    def to_canonical_str(self) -> str:
        sep = f" {self.op} "
        child_strs = sorted([c.to_canonical_str() for c in self.operands])
        return f"({sep.join(child_strs)})"


@dataclass
class NotNode(ASTNode):
    operand: ASTNode

    def evaluate(self, ticket: Dict[str, Any]) -> bool:
        return not self.operand.evaluate(ticket)

    def to_canonical_str(self) -> str:
        return f"NOT({self.operand.to_canonical_str()})"


@dataclass
class UnsupportedNode(ASTNode):
    raw_text: str
    reason: str

    def evaluate(self, ticket: Dict[str, Any]) -> bool:
        # Unsupported nodes cannot be deterministically evaluated
        return False

    def to_canonical_str(self) -> str:
        return f"UNSUPPORTED[{self.reason}]: {self.raw_text}"
