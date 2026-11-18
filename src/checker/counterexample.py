"""
Concrete Ticket Counterexample Generator.
Performs boundary probing and domain constraint search to find concrete ticket inputs
that demonstrate behavioral divergence between effective requirements and implementations.
"""

from typing import Dict, List, Optional, Any, Tuple
from src.contracts.models import Counterexample
from src.contracts.dsl_ast import ASTNode, NumericInterval
from src.effective_requirements.engine import EffectiveRequirement


class CounterexampleGenerator:
    """Generates concrete counterexamples demonstrating routing discrepancies."""

    @classmethod
    def search_counterexample(
        cls,
        effective_rules: List[EffectiveRequirement],
        effective_fallback: str,
        actual_evaluator_fn,  # callable(ticket) -> actual_action
        threshold_hints: Optional[List[float]] = None,
        field_hints: Optional[List[str]] = None,
    ) -> Optional[Counterexample]:
        """
        Searches the ticket feature space for a concrete ticket input where
        expected_route != actual_route.
        """
        # Collect boundary probe points
        probes = cls._generate_candidate_tickets(effective_rules, threshold_hints)

        for ticket in probes:
            expected_route = cls._evaluate_effective(effective_rules, effective_fallback, ticket)
            actual_route = actual_evaluator_fn(ticket)

            if expected_route != actual_route:
                # Find the specific rule where divergence originated
                violating_rule_id = cls._identify_violating_rule(effective_rules, ticket, expected_route)
                evidence = (
                    f"Behavioral mismatch detected on concrete input {ticket}: "
                    f"Expected route '{expected_route}' under effective requirements, "
                    f"but actual implementation routed to '{actual_route}'."
                )
                return Counterexample(
                    ticket_input=ticket,
                    expected_route=expected_route,
                    actual_route=actual_route,
                    violating_rule=violating_rule_id,
                    evidence=evidence,
                )

        return None

    @classmethod
    def _evaluate_effective(
        cls,
        ordered_rules: List[EffectiveRequirement],
        fallback_action: str,
        ticket: Dict[str, Any]
    ) -> str:
        for req in ordered_rules:
            if req.is_supported and req.parsed_ast.evaluate(ticket):
                return req.action
        return fallback_action

    @classmethod
    def _identify_violating_rule(
        cls,
        ordered_rules: List[EffectiveRequirement],
        ticket: Dict[str, Any],
        expected_route: str
    ) -> Optional[str]:
        for req in ordered_rules:
            if req.is_supported and req.parsed_ast.evaluate(ticket):
                return req.rule_id
        return None

    @classmethod
    def _generate_candidate_tickets(
        cls,
        effective_rules: List[EffectiveRequirement],
        extra_thresholds: Optional[List[float]] = None
    ) -> List[Dict[str, Any]]:
        # Gather all numeric thresholds from effective rules
        thresholds = {0.0, 10.0, 20.0, 25.0, 30.0, 35.0, 60.0}
        if extra_thresholds:
            thresholds.update(extra_thresholds)

        for req in effective_rules:
            cls._extract_thresholds(req.parsed_ast, thresholds)

        # Generate probe points around each threshold (+/- 1, +/- 0.1, exactly on boundary)
        wait_times: set = set()
        for t in thresholds:
            wait_times.update([
                max(0.0, t - 1.0),
                max(0.0, t - 0.01),
                t,
                t + 0.01,
                t + 1.0,
            ])

        sorted_wait_times = sorted(list(wait_times))
        categories = [None, "billing", "technical", "general"]
        urgencies = ["urgent", "normal", "low"]
        vip_options = [False, True]

        candidates: List[Dict[str, Any]] = []
        for cat in categories:
            for urg in urgencies:
                for vip in vip_options:
                    for wt in sorted_wait_times:
                        candidates.append({
                            "category": cat,
                            "urgency": urg,
                            "wait_time": wt,
                            "wait_time_minutes": wt,
                            "is_vip": vip,
                        })

        return candidates

    @classmethod
    def _extract_thresholds(cls, node: ASTNode, out_set: set):
        if isinstance(node, NumericInterval):
            if node.min_val != -float("inf"):
                out_set.add(node.min_val)
            if node.max_val != float("inf"):
                out_set.add(node.max_val)
