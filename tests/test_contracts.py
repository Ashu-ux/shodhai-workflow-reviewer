"""
Unit tests for Core Data Contracts, Serialization, and Validation.
"""

import unittest
import json
from src.contracts.models import (
    SourceRequirement,
    StructuredRule,
    Specification,
    WorkflowNode,
    WorkflowGraph,
    LinkedPythonSnippet,
    ApprovalRecord,
    ReviewBundle,
    ReviewReport,
    ReviewCoverage,
    ProvenanceRecord,
)


class TestContracts(unittest.TestCase):

    def test_source_requirement_creation_and_fields(self):
        req = SourceRequirement(
            id="R1",
            version="1.0",
            section="Policy.md#Section1",
            title="Category Check",
            condition_dsl="category is None",
            action="manual_review",
            precedence=1,
            prose="Missing category tickets must be reviewed manually."
        )
        self.assertEqual(req.id, "R1")
        self.assertEqual(req.action, "manual_review")
        self.assertTrue(req.is_supported)

    def test_bundle_serialization_roundtrip(self):
        req = SourceRequirement("R1", "1.0", "Sec1", "Title", "cat is None", "manual", 1, "Prose")
        spec = Specification("SPEC-1", "1.0", [StructuredRule("R1", "cat is None", "manual", 1)], "normal")
        wf = WorkflowGraph("WF-1", "1.0", "N1", {"N1": WorkflowNode("N1", "action", action="normal")})
        snip = LinkedPythonSnippet("S1", "R1", "1.0", "r.py", "route", "def route(t): return 'normal'")
        appr = ApprovalRecord("A1", "R1", "UPDATE_THRESHOLD", None, None, "APPROVED", "eng", "2026-01-01T00:00:00Z")

        bundle = ReviewBundle(
            bundle_id="b_test",
            name="Test Bundle",
            description="Unit test bundle",
            source_requirements=[req],
            specification=spec,
            workflow_graph=wf,
            python_snippets=[snip],
            approval_records=[appr],
            expected_status="PASS"
        )

        b_dict = bundle.to_dict()
        reconstructed = ReviewBundle.from_dict(b_dict)

        self.assertEqual(reconstructed.bundle_id, "b_test")
        self.assertEqual(len(reconstructed.source_requirements), 1)
        self.assertEqual(reconstructed.specification.id, "SPEC-1")
        self.assertEqual(reconstructed.workflow_graph.id, "WF-1")
        self.assertEqual(len(reconstructed.approval_records), 1)


if __name__ == "__main__":
    unittest.main()
