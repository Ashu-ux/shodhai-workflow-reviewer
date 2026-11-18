"""
Unit tests for Concrete Counterexample Search and Generation.
"""

import unittest
from src.contracts.models import SourceRequirement
from src.effective_requirements.engine import EffectiveRequirementsEngine
from src.checker.counterexample import CounterexampleGenerator


class TestCounterexample(unittest.TestCase):

    def test_search_counterexample_on_threshold_shift(self):
        source = [
            SourceRequirement("R1", "1.0", "Sec", "Title", "wait_time >= 30 minutes", "escalation", 1, "Prose")
        ]
        derivation = EffectiveRequirementsEngine.derive(source, [])
        ordered = derivation.ordered_rules

        # Actual implementation uses 25 minutes instead of 30 minutes
        def actual_fn(ticket):
            if ticket.get("wait_time_minutes", 0) >= 25:
                return "escalation"
            return "normal_queue"

        cex = CounterexampleGenerator.search_counterexample(
            effective_rules=ordered,
            effective_fallback="normal_queue",
            actual_evaluator_fn=actual_fn,
        )

        self.assertIsNotNone(cex)
        self.assertNotEqual(cex.expected_route, cex.actual_route)
        # Ticket wait time should be between 25 and 30
        wt = cex.ticket_input.get("wait_time_minutes")
        self.assertTrue(25.0 <= wt < 30.0)


if __name__ == "__main__":
    unittest.main()
