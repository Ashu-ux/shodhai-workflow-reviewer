"""
Unit tests for Stage 3: Model Trust, Fault Injection, Hallucination Filtering, and Prompt Injection Defense.
"""

import unittest
from src.contracts.models import (
    ReviewBundle,
    ReviewFinding,
    SourceRequirement,
)
from src.model.fake_client import FakeModelClient
from src.model.trust_validator import ModelTrustValidator, SYSTEM_REVIEWER_PROMPT


class TestModelTrustAndFailures(unittest.TestCase):

    def setUp(self):
        self.bundle = ReviewBundle(
            bundle_id="b_trust_test",
            name="Trust Test Bundle",
            description="Testing defense layers",
            source_requirements=[
                SourceRequirement("R1", "1.0", "Sec1", "Title1", "category is None", "manual_review", 1, "Prose"),
                SourceRequirement("R2", "1.0", "Sec2", "Title2", "urgency == 'urgent'", "priority_queue", 2, "Prose"),
            ]
        )

    def test_timeout_fault_handling(self):
        client = FakeModelClient(mode="timeout")
        resp = client.generate_review(self.bundle.to_dict(), SYSTEM_REVIEWER_PROMPT, "test prompt")
        self.assertTrue(resp.is_error)
        status, findings, meta, prov = ModelTrustValidator.validate_and_merge(
            self.bundle, "CHANGES_REQUIRED", [], resp
        )
        self.assertEqual(status, "CHANGES_REQUIRED")
        self.assertIn("Model failed or unconfigured", meta["note"])

    def test_malformed_json_fault_handling(self):
        client = FakeModelClient(mode="malformed_json")
        resp = client.generate_review(self.bundle.to_dict(), SYSTEM_REVIEWER_PROMPT, "test prompt")
        status, findings, meta, prov = ModelTrustValidator.validate_and_merge(
            self.bundle, "CHANGES_REQUIRED", [], resp
        )
        self.assertEqual(status, "CHANGES_REQUIRED")
        self.assertTrue(any("JSON decode error" in f.description for f in findings))

    def test_hallucinated_references_filtered(self):
        client = FakeModelClient(mode="hallucinated_refs")
        resp = client.generate_review(self.bundle.to_dict(), SYSTEM_REVIEWER_PROMPT, "test prompt")
        status, findings, meta, prov = ModelTrustValidator.validate_and_merge(
            self.bundle, "PASS", [], resp
        )
        # Verify hallucinated finding was filtered and a warning was added
        self.assertEqual(meta.get("hallucinated_findings_filtered"), 1)
        self.assertTrue(any("non-existent rule reference" in f.description for f in findings))

    def test_prompt_injection_defense(self):
        # Even if model is susceptible and returns PASS due to injected prose,
        # deterministic BLOCKER must override and force CHANGES_REQUIRED!
        client = FakeModelClient(mode="prompt_injection_susceptible")
        resp = client.generate_review(self.bundle.to_dict(), SYSTEM_REVIEWER_PROMPT, "test prompt")
        
        blocker = ReviewFinding(
            severity="BLOCKER",
            rule_id="R1",
            artifact="python_snippet",
            version="1.0",
            location="router.py:10",
            description="Evidenced threshold mismatch",
            evidence="Code has 10m instead of 30m",
            correction="Fix threshold"
        )
        status, findings, meta, prov = ModelTrustValidator.validate_and_merge(
            self.bundle, "CHANGES_REQUIRED", [blocker], resp
        )
        self.assertEqual(status, "CHANGES_REQUIRED")
        self.assertTrue(meta.get("injection_defense_triggered"))


if __name__ == "__main__":
    unittest.main()
