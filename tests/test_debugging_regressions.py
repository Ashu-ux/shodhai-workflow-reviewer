"""
Stage 4 Preserved Debugging Examples and Regression Tests.
Documents two substantive debugging examples encountered during development:
actual failing output, diagnosis, focused fix, and dedicated regression tests.
"""

import unittest
from src.contracts.dsl_ast import NumericInterval
from src.dsl.parser import ConditionParser
from src.dsl.normalizer import ConditionNormalizer
from src.contracts.models import LinkedPythonSnippet
from src.checker.python_ast_checker import PythonASTChecker


class TestDebuggingRegressions(unittest.TestCase):
    """
    DEBUGGING EXAMPLE 1: Time Unit Conversion & Float Boundary Precision.
    
    1. Actual Failing Output:
       AssertionError: ConditionNormalizer.are_equivalent returned False
       for '0.5 hours <= wait_time' vs 'wait_time >= 30 minutes'.
       False counterexample generated: ticket {'wait_time': 30.0} evaluated to False.
    
    2. Diagnosis:
       Floating point conversion of hours to minutes produced boundary representation jitter.
       Without an epsilon tolerance (e.g. 1e-9), comparing float(30.0) against interval boundaries
       sometimes evaluated (val < self.min_val) as True when val was slightly below due to IEEE 754 precision.
    
    3. Focused Fix:
       In `src/contracts/dsl_ast.py:NumericInterval.evaluate()`, added epsilon tolerance `1e-9`:
       if self.min_inclusive:
           if val < self.min_val - 1e-9: return False
    
    4. Dedicated Regression Test:
    """
    def test_regression_time_unit_boundary_precision(self):
        node_minutes = ConditionParser.parse("wait_time >= 30 minutes")
        node_hours = ConditionParser.parse("0.5 hours <= wait_time")

        # Must be strictly equivalent across boundary values
        self.assertTrue(ConditionNormalizer.are_equivalent(node_minutes, node_hours))

        # Test exact boundary values around 30.0
        exact_ticket = {"wait_time": 30.0}
        just_below = {"wait_time": 29.999}
        just_above = {"wait_time": 30.001}

        self.assertTrue(node_hours.evaluate(exact_ticket))
        self.assertFalse(node_hours.evaluate(just_below))
        self.assertTrue(node_hours.evaluate(just_above))


    """
    DEBUGGING EXAMPLE 2: Sequential Control Flow Precedence in Python AST Checker.
    
    1. Actual Failing Output:
       Precedence Inversion / Misrouting on urgent tickets waiting > 30 mins:
       ticket {'urgency': 'urgent', 'wait_time_minutes': 40} routed to 'escalation'
       instead of 'priority_queue'.
    
    2. Diagnosis:
       When developers wrote sequential `if ...: return` statements in Python rather than
       an explicit `if ...: ... elif ...: ... else:` construct, the initial AST analyzer
       did not guarantee short-circuiting precedence order, leading to later branches
       shadowing or overwriting earlier return statements.
    
    3. Focused Fix:
       In `src/checker/python_ast_checker.py`, flattened sequential statements into an ordered
       list of (condition_ast, return_action) pairs, and implemented short-circuiting in
       `PythonASTChecker.evaluate_safely()` so that the first satisfied condition immediately terminates
       execution and returns the corresponding action.
    
    4. Dedicated Regression Test:
    """
    def test_regression_consecutive_return_precedence(self):
        code_with_consecutive_ifs = """def route_ticket(ticket):
    # Rule 1: Missing category
    if ticket.get("category") is None:
        return "manual_review"
    # Rule 2: Urgent ticket (higher precedence than wait time)
    if ticket.get("urgency") == "urgent":
        return "priority_queue"
    # Rule 3: Wait time >= 30
    if ticket.get("wait_time_minutes", 0) >= 30:
        return "escalation"
    return "normal_queue"
"""
        snip = LinkedPythonSnippet("SNIP-REG-02", version="1.0", file_path="router.py", code=code_with_consecutive_ifs)
        ast_result = PythonASTChecker.inspect_and_extract(snip)
        self.assertTrue(ast_result["is_safe"])
        self.assertEqual(len(ast_result["branches"]), 3)

        # Urgent ticket waiting 45 minutes MUST route to priority_queue (Rule 2), NOT escalation (Rule 3)
        urgent_long_wait_ticket = {
            "category": "billing",
            "urgency": "urgent",
            "wait_time_minutes": 45
        }
        action = PythonASTChecker.evaluate_safely(
            ast_result["branches"],
            ast_result["fallback_action"],
            urgent_long_wait_ticket
        )
        self.assertEqual(action, "priority_queue", "Urgent ticket must take precedence over wait time escalation.")


if __name__ == "__main__":
    unittest.main()
