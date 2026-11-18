"""
Precedence and Rule Interaction / Shadowing Analyzer.
Verifies evaluation order, detects precedence inversions, rule shadowing,
and unreachable condition branches.
"""

from typing import List, Dict, Tuple, Optional, Any
from src.contracts.dsl_ast import ASTNode
from src.effective_requirements.engine import EffectiveRequirement


class PrecedenceAnalyzer:
    """Detects precedence order conflicts and condition shadowing between rules."""

    @classmethod
    def analyze_order_agreement(
        cls,
        expected_order: List[str],  # List of rule_ids in required precedence order
        actual_order: List[str]     # List of rule_ids as evaluated in implementation
    ) -> List[Dict[str, Any]]:
        """
        Checks whether the evaluation order in the implementation respects
        the required precedence order among common rules.
        """
        mismatches: List[Dict[str, Any]] = []
        
        # Filter to common rules
        common_rules = [r for r in actual_order if r in expected_order]
        expected_filtered = [r for r in expected_order if r in common_rules]

        for i in range(len(common_rules)):
            for j in range(i + 1, len(common_rules)):
                rule_a = common_rules[i]
                rule_b = common_rules[j]
                
                # Check their indices in expected order
                exp_idx_a = expected_filtered.index(rule_a)
                exp_idx_b = expected_filtered.index(rule_b)
                
                if exp_idx_a > exp_idx_b:
                    # Inverted precedence! Rule A evaluated before Rule B, but Rule B has higher precedence
                    mismatches.append({
                        "type": "PRECEDENCE_INVERSION",
                        "higher_priority_rule": rule_b,
                        "lower_priority_rule": rule_a,
                        "description": (
                            f"Precedence inversion detected: Rule '{rule_b}' (precedence {exp_idx_b + 1}) "
                            f"is evaluated after Rule '{rule_a}' (precedence {exp_idx_a + 1}). "
                            f"Tickets satisfying both rules will incorrectly take the route of '{rule_a}'."
                        )
                    })

        return mismatches

    @classmethod
    def detect_shadowing(
        cls,
        ordered_rules: List[EffectiveRequirement],
        domain_samples: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Detects if a later rule is completely shadowed by earlier rules
        and can never be satisfied by any ticket in the domain.
        """
        shadowed: List[Dict[str, Any]] = []

        for i, rule in enumerate(ordered_rules):
            # Check if there exists at least one sample ticket where rule is satisfied
            # AND no earlier rule is satisfied
            can_fire = False
            for sample in domain_samples:
                earlier_fired = any(ordered_rules[k].parsed_ast.evaluate(sample) for k in range(i))
                if not earlier_fired and rule.parsed_ast.evaluate(sample):
                    can_fire = True
                    break

            if not can_fire:
                shadowed.append({
                    "rule_id": rule.rule_id,
                    "location": f"RulePrecedence:{rule.precedence}",
                    "description": f"Rule '{rule.rule_id}' is completely shadowed by higher-precedence rules and is unreachable."
                })

        return shadowed
