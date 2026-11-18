"""
Condition Normalizer and Equivalence Checker.
Applies De Morgan's laws, flattens associative boolean operations,
and verifies semantic equivalence between condition formulations.
"""

import math
from typing import List, Dict, Any, Tuple, Optional
from src.contracts.dsl_ast import (
    ASTNode,
    MissingValueCheck,
    NumericInterval,
    EqualityCheck,
    BoolOpNode,
    NotNode,
    UnsupportedNode,
)


class ConditionNormalizer:
    """Transforms AST nodes into canonical normal forms and checks equivalence."""

    @classmethod
    def normalize(cls, node: ASTNode) -> ASTNode:
        """Applies algebraic simplifications and De Morgan transformations."""
        if isinstance(node, NotNode):
            inner = cls.normalize(node.operand)
            # Double negation: NOT(NOT(X)) -> X
            if isinstance(inner, NotNode):
                return inner.operand
            # De Morgan: NOT(AND(A, B)) -> OR(NOT(A), NOT(B))
            if isinstance(inner, BoolOpNode) and inner.op == "AND":
                return BoolOpNode(
                    op="OR",
                    operands=[cls.normalize(NotNode(operand=op)) for op in inner.operands]
                )
            # De Morgan: NOT(OR(A, B)) -> AND(NOT(A), NOT(B))
            if isinstance(inner, BoolOpNode) and inner.op == "OR":
                return BoolOpNode(
                    op="AND",
                    operands=[cls.normalize(NotNode(operand=op)) for op in inner.operands]
                )
            # Inversion of interval: NOT( [min, inf) ) -> (-inf, min)
            if isinstance(inner, NumericInterval):
                if inner.min_val != -math.inf and inner.max_val == math.inf:
                    return NumericInterval(
                        field_name=inner.field_name,
                        min_val=-math.inf,
                        min_inclusive=False,
                        max_val=inner.min_val,
                        max_inclusive=not inner.min_inclusive,
                        unit=inner.unit
                    )
                if inner.min_val == -math.inf and inner.max_val != math.inf:
                    return NumericInterval(
                        field_name=inner.field_name,
                        min_val=inner.max_val,
                        min_inclusive=not inner.max_inclusive,
                        max_val=math.inf,
                        max_inclusive=False,
                        unit=inner.unit
                    )
            # Inversion of missing value check
            if isinstance(inner, MissingValueCheck):
                return MissingValueCheck(field_name=inner.field_name, is_missing=not inner.is_missing)
            
            return NotNode(operand=inner)

        elif isinstance(node, BoolOpNode):
            flattened_operands: List[ASTNode] = []
            for child in node.operands:
                norm_child = cls.normalize(child)
                # Flatten associative operators: AND(AND(a, b), c) -> AND(a, b, c)
                if isinstance(norm_child, BoolOpNode) and norm_child.op == node.op:
                    flattened_operands.extend(norm_child.operands)
                else:
                    flattened_operands.append(norm_child)
            
            # Sort canonical representations for deterministic comparison
            flattened_operands.sort(key=lambda x: x.to_canonical_str())
            return BoolOpNode(op=node.op, operands=flattened_operands)

        return node

    @classmethod
    def are_equivalent(cls, node1: ASTNode, node2: ASTNode, domain_samples: Optional[List[Dict[str, Any]]] = None) -> bool:
        """
        Determines semantic equivalence by:
        1. Checking canonical string representations.
        2. If string differs, verifying exhaustive evaluation across domain test points.
        """
        norm1 = cls.normalize(node1)
        norm2 = cls.normalize(node2)
        
        # 1. Direct syntactic equivalence after normalization
        if norm1.to_canonical_str() == norm2.to_canonical_str():
            return True
        
        # Special check for direct NumericInterval equivalence
        if isinstance(norm1, NumericInterval) and isinstance(norm2, NumericInterval):
            return norm1.equals(norm2)

        # 2. Semantic evaluation over the domain feature grid
        if domain_samples is None:
            domain_samples = cls.generate_domain_samples()

        for sample in domain_samples:
            if norm1.evaluate(sample) != norm2.evaluate(sample):
                return False

        return True

    @classmethod
    def generate_domain_samples(cls) -> List[Dict[str, Any]]:
        """Generates representative test ticket features covering boundary and categorical values."""
        categories = [None, "billing", "technical", "general", ""]
        urgencies = ["urgent", "normal", "low"]
        wait_times = [0.0, 10.0, 24.9, 25.0, 25.1, 29.9, 30.0, 30.1, 45.0, 60.0]
        vip_flags = [True, False]

        samples = []
        for cat in categories:
            for urg in urgencies:
                for wt in wait_times:
                    for vip in vip_flags:
                        samples.append({
                            "category": cat,
                            "urgency": urg,
                            "wait_time": wt,
                            "wait_time_minutes": wt,
                            "is_vip": vip,
                        })
        return samples
