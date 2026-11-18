"""
Restricted Python AST Inspector and Safe Evaluator.
Performs syntax checking, security filtering, and extracts semantic routing logic
without executing arbitrary untrusted Python code.
"""

import ast
import re
from typing import Dict, List, Optional, Tuple, Any
from src.contracts.dsl_ast import (
    ASTNode,
    MissingValueCheck,
    NumericInterval,
    EqualityCheck,
    BoolOpNode,
    NotNode,
    UnsupportedNode,
)
from src.contracts.models import LinkedPythonSnippet


ALLOWED_AST_NODES = (
    ast.Module,
    ast.FunctionDef,
    ast.arguments,
    ast.arg,
    ast.If,
    ast.Compare,
    ast.BoolOp,
    ast.UnaryOp,
    ast.Constant,
    ast.Name,
    ast.Return,
    ast.Expr,
    ast.Load,
    ast.Gt,
    ast.GtE,
    ast.Lt,
    ast.LtE,
    ast.Eq,
    ast.NotEq,
    ast.Is,
    ast.IsNot,
    ast.And,
    ast.Or,
    ast.Not,
    ast.Subscript,
    ast.Attribute,
    ast.Call,
    ast.Pass,
)


class PythonASTChecker:
    """Safely inspects and semantically evaluates restricted Python routing snippets."""

    @classmethod
    def inspect_and_extract(cls, snippet: LinkedPythonSnippet) -> Dict[str, Any]:
        """
        Parses code using ast.parse, validates restricted safety profile,
        and extracts sequential (condition_ast, return_action) branches.
        """
        if not snippet.code or not snippet.code.strip():
            return {
                "is_safe": False,
                "syntax_valid": False,
                "error": "Empty python snippet code.",
                "branches": [],
                "fallback_action": None,
            }

        try:
            tree = ast.parse(snippet.code)
        except SyntaxError as e:
            return {
                "is_safe": False,
                "syntax_valid": False,
                "error": f"Python SyntaxError at line {e.lineno}: {e.msg}",
                "branches": [],
                "fallback_action": None,
            }

        # 1. Security Check: verify all AST nodes are in ALLOWED_AST_NODES
        for node in ast.walk(tree):
            if not isinstance(node, ALLOWED_AST_NODES):
                return {
                    "is_safe": False,
                    "syntax_valid": True,
                    "error": f"Disallowed Python AST construct '{type(node).__name__}' detected. Arbitrary execution blocked.",
                    "branches": [],
                    "fallback_action": None,
                }
            # Verify any function calls are strictly limited to ticket.get(...)
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute) and node.func.attr == "get":
                    pass  # ticket.get is allowed
                else:
                    return {
                        "is_safe": False,
                        "syntax_valid": True,
                        "error": f"Disallowed function call detected in restricted code.",
                        "branches": [],
                        "fallback_action": None,
                    }

        # 2. Find entry function
        target_func: Optional[ast.FunctionDef] = None
        for item in tree.body:
            if isinstance(item, ast.FunctionDef):
                if item.name == snippet.entry_function or not target_func:
                    target_func = item

        if not target_func:
            return {
                "is_safe": True,
                "syntax_valid": True,
                "error": f"Entry function '{snippet.entry_function}' not found in code.",
                "branches": [],
                "fallback_action": None,
            }

        # 3. Extract sequential routing branches
        branches: List[Tuple[ASTNode, str]] = []
        fallback_action: Optional[str] = None

        cls._extract_branches_from_body(target_func.body, branches)

        # Check the last statement for a top-level return (fallback)
        if target_func.body and isinstance(target_func.body[-1], ast.Return):
            last_ret = target_func.body[-1]
            if isinstance(last_ret.value, ast.Constant) and isinstance(last_ret.value.value, str):
                fallback_action = last_ret.value.value

        return {
            "is_safe": True,
            "syntax_valid": True,
            "error": None,
            "branches": branches,
            "fallback_action": fallback_action,
        }

    @classmethod
    def _extract_branches_from_body(
        cls,
        statements: List[ast.stmt],
        branches: List[Tuple[ASTNode, str]]
    ):
        for stmt in statements:
            if isinstance(stmt, ast.If):
                cond_ast = cls._convert_ast_condition(stmt.test)
                # Find return inside if body
                ret_val = cls._find_return_value(stmt.body)
                if ret_val:
                    branches.append((cond_ast, ret_val))
                # If there are elif branches (stored in stmt.orelse)
                if stmt.orelse:
                    cls._extract_branches_from_body(stmt.orelse, branches)

    @classmethod
    def _find_return_value(cls, body: List[ast.stmt]) -> Optional[str]:
        for s in body:
            if isinstance(s, ast.Return):
                if isinstance(s.value, ast.Constant) and isinstance(s.value.value, str):
                    return s.value.value
        return None

    @classmethod
    def _convert_ast_condition(cls, test_node: ast.expr) -> ASTNode:
        """Converts Python AST test expression into our canonical ASTNode."""
        # Unary Not
        if isinstance(test_node, ast.UnaryOp) and isinstance(test_node.op, ast.Not):
            inner = cls._convert_ast_condition(test_node.operand)
            return NotNode(operand=inner)

        # Boolean ops: and, or
        if isinstance(test_node, ast.BoolOp):
            op_name = "AND" if isinstance(test_node.op, ast.And) else "OR"
            operands = [cls._convert_ast_condition(v) for v in test_node.values]
            return BoolOpNode(op=op_name, operands=operands)

        # Comparisons
        if isinstance(test_node, ast.Compare):
            left = test_node.left
            if len(test_node.ops) == 1 and len(test_node.comparators) == 1:
                op = test_node.ops[0]
                right = test_node.comparators[0]
                return cls._parse_compare_op(left, op, right)

        # Fallback to unsupported node
        code_str = ast.unparse(test_node) if hasattr(ast, "unparse") else "ast.expr"
        return UnsupportedNode(raw_text=code_str, reason="Unsupported Python condition structure")

    @classmethod
    def _parse_compare_op(cls, left: ast.expr, op: ast.cmpop, right: ast.expr) -> ASTNode:
        # Extract field name from left (e.g. ticket.get("category") or ticket["category"] or ticket.category)
        field_name = cls._extract_field_name(left)
        if not field_name:
            field_name = cls._extract_field_name(right)
            if field_name:
                # Swapped operands: flip op
                left, right = right, left
                op = cls._flip_cmpop(op)

        if not field_name:
            return UnsupportedNode(raw_text="Unknown comparison", reason="Cannot identify ticket field")

        # Check for Is / IsNot None
        if isinstance(op, ast.Is) and isinstance(right, ast.Constant) and right.value is None:
            return MissingValueCheck(field_name=field_name, is_missing=True)
        if isinstance(op, ast.IsNot) and isinstance(right, ast.Constant) and right.value is None:
            return MissingValueCheck(field_name=field_name, is_missing=False)
        if isinstance(op, ast.Eq) and isinstance(right, ast.Constant) and right.value is None:
            return MissingValueCheck(field_name=field_name, is_missing=True)

        # Check for String Equality
        if isinstance(op, (ast.Eq, ast.NotEq)) and isinstance(right, ast.Constant) and isinstance(right.value, str):
            op_str = "==" if isinstance(op, ast.Eq) else "!="
            return EqualityCheck(field_name=field_name, op=op_str, expected_value=right.value)

        # Check for Boolean Equality
        if isinstance(op, (ast.Eq, ast.NotEq)) and isinstance(right, ast.Constant) and isinstance(right.value, bool):
            op_str = "==" if isinstance(op, ast.Eq) else "!="
            return EqualityCheck(field_name=field_name, op=op_str, expected_value=right.value)

        # Check for Numeric Intervals
        if isinstance(right, ast.Constant) and isinstance(right.value, (int, float)):
            val = float(right.value)
            if isinstance(op, ast.GtE):
                return NumericInterval(field_name=field_name, min_val=val, min_inclusive=True)
            elif isinstance(op, ast.Gt):
                return NumericInterval(field_name=field_name, min_val=val, min_inclusive=False)
            elif isinstance(op, ast.LtE):
                return NumericInterval(field_name=field_name, max_val=val, max_inclusive=True)
            elif isinstance(op, ast.Lt):
                return NumericInterval(field_name=field_name, max_val=val, max_inclusive=False)
            elif isinstance(op, ast.Eq):
                return NumericInterval(field_name=field_name, min_val=val, min_inclusive=True, max_val=val, max_inclusive=True)

        return UnsupportedNode(raw_text=f"Comparison on {field_name}", reason="Unsupported comparison operand")

    @classmethod
    def _flip_cmpop(cls, op: ast.cmpop) -> ast.cmpop:
        if isinstance(op, ast.Gt): return ast.Lt()
        if isinstance(op, ast.GtE): return ast.LtE()
        if isinstance(op, ast.Lt): return ast.Gt()
        if isinstance(op, ast.LtE): return ast.GtE()
        return op

    @classmethod
    def _extract_field_name(cls, expr: ast.expr) -> Optional[str]:
        # ticket.get("field") or ticket.get("field", default)
        if isinstance(expr, ast.Call) and isinstance(expr.func, ast.Attribute) and expr.func.attr == "get":
            if expr.args and isinstance(expr.args[0], ast.Constant) and isinstance(expr.args[0].value, str):
                return expr.args[0].value
        # ticket["field"]
        if isinstance(expr, ast.Subscript) and isinstance(expr.slice, ast.Constant) and isinstance(expr.slice.value, str):
            return expr.slice.value
        # ticket.field
        if isinstance(expr, ast.Attribute) and isinstance(expr.value, ast.Name) and expr.value.id == "ticket":
            return expr.attr
        # bare variable name: e.g. wait_time
        if isinstance(expr, ast.Name):
            return expr.id
        return None

    @classmethod
    def evaluate_safely(
        cls,
        branches: List[Tuple[ASTNode, str]],
        fallback_action: Optional[str],
        ticket: Dict[str, Any]
    ) -> str:
        """Safely simulates the routing logic on a ticket input using the extracted AST."""
        for cond_ast, action in branches:
            if cond_ast.evaluate(ticket):
                return action
        return fallback_action or "normal_queue"
