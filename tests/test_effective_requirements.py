"""
Unit tests for Stage 1: Effective Requirements Derivation and Contradiction Detection.
"""

import unittest
from src.contracts.models import SourceRequirement, ApprovalRecord
from src.effective_requirements.engine import EffectiveRequirementsEngine


class TestEffectiveRequirements(unittest.TestCase):

    def setUp(self):
        self.base_reqs = [
            SourceRequirement("R1", "1.0", "Sec1", "Missing Cat", "category is None", "manual_review", 1, "Prose"),
            SourceRequirement("R2", "1.0", "Sec2", "Urgent", "urgency == 'urgent'", "priority_queue", 2, "Prose"),
            SourceRequirement("R3", "1.0", "Sec3", "Wait", "wait_time >= 30 minutes", "escalation", 3, "Prose"),
        ]

    def test_apply_valid_approved_change(self):
        approvals = [
            ApprovalRecord("CHG-1", "R3", "UPDATE_THRESHOLD", "wait_time >= 25 minutes", None, "APPROVED", "lead", "2026-01-15T00:00:00Z")
        ]
        result = EffectiveRequirementsEngine.derive(self.base_reqs, approvals)
        self.assertEqual(len(result.contradictions), 0)
        self.assertEqual(len(result.unapproved_records), 0)
        eff_r3 = result.effective_requirements["R3"]
        self.assertEqual(eff_r3.condition_dsl, "wait_time >= 25 minutes")
        self.assertIn("CHG-1", eff_r3.applied_changes)

    def test_ignore_unapproved_or_proposed_change(self):
        approvals = [
            ApprovalRecord("CHG-PROPOSED", "R3", "UPDATE_THRESHOLD", "wait_time >= 20 minutes", None, "PROPOSED", "eng", "2026-01-15T00:00:00Z")
        ]
        result = EffectiveRequirementsEngine.derive(self.base_reqs, approvals)
        self.assertEqual(len(result.unapproved_records), 1)
        eff_r3 = result.effective_requirements["R3"]
        # Effective requirement remains 30 minutes!
        self.assertEqual(eff_r3.condition_dsl, "wait_time >= 30 minutes")

    def test_detect_contradictory_approved_records(self):
        approvals = [
            ApprovalRecord("CHG-A", "R3", "UPDATE_THRESHOLD", "wait_time >= 20 minutes", None, "APPROVED", "lead_a", "2026-01-15T00:00:00Z"),
            ApprovalRecord("CHG-B", "R3", "UPDATE_THRESHOLD", "wait_time >= 25 minutes", None, "APPROVED", "lead_b", "2026-01-15T00:00:00Z"),
        ]
        result = EffectiveRequirementsEngine.derive(self.base_reqs, approvals)
        self.assertEqual(len(result.contradictions), 1)
        self.assertEqual(result.contradictions[0]["target_rule_id"], "R3")


if __name__ == "__main__":
    unittest.main()
