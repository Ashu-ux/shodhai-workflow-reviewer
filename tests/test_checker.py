"""
Unit tests for Stage 2: Workflow Graph Traversal, Restricted Python AST Checker, and Precedence.
"""

import unittest
from src.contracts.models import (
    WorkflowGraph,
    WorkflowNode,
    LinkedPythonSnippet,
)
from src.checker.graph_traversal import GraphTraversalAnalyzer
from src.checker.python_ast_checker import PythonASTChecker
from src.checker.precedence import PrecedenceAnalyzer


class TestChecker(unittest.TestCase):

    def test_graph_cycle_detection(self):
        # Graph with cyclic loop N1 -> N2 -> N1
        nodes = {
            "N1": WorkflowNode("N1", "condition", "R1", "category is None", "N2", "N2"),
            "N2": WorkflowNode("N2", "condition", "R2", "urgency == 'urgent'", "N1", "N1"),
        }
        graph = WorkflowGraph("WF-CYCLE", "1.0", "N1", nodes)
        analysis = GraphTraversalAnalyzer.analyze(graph)
        self.assertFalse(analysis["is_valid"])
        self.assertTrue(any("cyclic" in err.lower() for err in analysis["errors"]))

    def test_restricted_python_ast_safety(self):
        # Attempting forbidden OS or loop construct in restricted Python snippet
        malicious_code = """def route_ticket(ticket):
    import os
    os.system("echo dangerous")
    return "manual_review"
"""
        snip = LinkedPythonSnippet("SNIP-MAL", code=malicious_code)
        result = PythonASTChecker.inspect_and_extract(snip)
        self.assertFalse(result["is_safe"])
        self.assertIn("Arbitrary execution blocked", result["error"])

    def test_precedence_inversion_detection(self):
        expected_order = ["R1", "R2", "R3"]
        actual_order = ["R1", "R3", "R2"]  # Inversion: R3 before R2
        mismatches = PrecedenceAnalyzer.analyze_order_agreement(expected_order, actual_order)
        self.assertEqual(len(mismatches), 1)
        self.assertEqual(mismatches[0]["higher_priority_rule"], "R2")
        self.assertEqual(mismatches[0]["lower_priority_rule"], "R3")


if __name__ == "__main__":
    unittest.main()
