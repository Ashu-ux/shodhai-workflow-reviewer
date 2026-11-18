"""
Unit tests for Routing Condition DSL Parser, Canonicalization, and Normalizer.
"""

import unittest
from src.dsl.parser import ConditionParser
from src.dsl.normalizer import ConditionNormalizer
from src.contracts.dsl_ast import (
    MissingValueCheck,
    NumericInterval,
    EqualityCheck,
    BoolOpNode,
    NotNode,
    UnsupportedNode,
)


class TestDSLAndNormalizer(unittest.TestCase):

    def test_missing_value_parsing(self):
        node1 = ConditionParser.parse("category is None")
        self.assertIsInstance(node1, MissingValueCheck)
        self.assertTrue(node1.is_missing)
        self.assertTrue(node1.evaluate({"category": None}))
        self.assertFalse(node1.evaluate({"category": "billing"}))

        node2 = ConditionParser.parse("missing category")
        self.assertIsInstance(node2, MissingValueCheck)
        self.assertTrue(node2.evaluate({}))

    def test_numeric_boundary_and_units(self):
        # 30 minutes inclusive
        node1 = ConditionParser.parse("wait_time >= 30 minutes")
        self.assertIsInstance(node1, NumericInterval)
        self.assertEqual(node1.min_val, 30.0)
        self.assertTrue(node1.min_inclusive)
        self.assertTrue(node1.evaluate({"wait_time": 30.0}))
        self.assertTrue(node1.evaluate({"wait_time": 30.1}))
        self.assertFalse(node1.evaluate({"wait_time": 29.9}))

        # 0.5 hours (should canonicalize to 30.0 minutes)
        node2 = ConditionParser.parse("wait_time >= 0.5 hours")
        self.assertIsInstance(node2, NumericInterval)
        self.assertEqual(node2.min_val, 30.0)
        self.assertTrue(ConditionNormalizer.are_equivalent(node1, node2))

        # Swapped operands: 30 <= wait_time
        node3 = ConditionParser.parse("30 <= wait_time")
        self.assertIsInstance(node3, NumericInterval)
        self.assertEqual(node3.min_val, 30.0)
        self.assertTrue(ConditionNormalizer.are_equivalent(node1, node3))

        # Strict inequality > 30 (not equivalent to >= 30)
        node4 = ConditionParser.parse("wait_time > 30")
        self.assertFalse(node4.min_inclusive)
        self.assertFalse(ConditionNormalizer.are_equivalent(node1, node4))
        self.assertFalse(node4.evaluate({"wait_time": 30.0}))

    def test_ordered_exceptions_unless(self):
        # A unless B -> A and not B
        node = ConditionParser.parse("urgency == 'urgent' unless is_vip == True")
        self.assertIsInstance(node, BoolOpNode)
        self.assertEqual(node.op, "AND")
        self.assertTrue(node.evaluate({"urgency": "urgent", "is_vip": False}))
        self.assertFalse(node.evaluate({"urgency": "urgent", "is_vip": True}))

    def test_de_morgan_and_equivalence(self):
        # not (urgency != 'urgent') -> urgency == 'urgent'
        n1 = ConditionParser.parse("urgency == 'urgent'")
        n2 = ConditionParser.parse("not (urgency != 'urgent')")
        self.assertTrue(ConditionNormalizer.are_equivalent(n1, n2))

    def test_unsupported_syntax_preservation(self):
        # Preserves visibility of ambiguous natural language
        raw_text = "distressed sentiment vibe"
        node = ConditionParser.parse(raw_text)
        self.assertIsInstance(node, UnsupportedNode)
        self.assertEqual(node.raw_text, raw_text)


if __name__ == "__main__":
    unittest.main()
