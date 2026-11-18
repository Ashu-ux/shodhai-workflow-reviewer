"""
Baseline Reviewer Checkpoint (v0.1).
Represents the initial prototype before AST semantic analysis,
boundary interval checking, precedence verification, and counterexample generation.
Used for controlled evaluation comparison against the final v1.0 engine.
"""

from typing import Dict, List, Any
from src.contracts.models import (
    ReviewBundle,
    ReviewReport,
    ReviewFinding,
    ReviewCoverage,
    ProvenanceRecord,
)


class BaselineReviewerV0:
    """Naive baseline reviewer relying on rule ID presence and substring matching."""

    @classmethod
    def review(cls, bundle: ReviewBundle) -> ReviewReport:
        findings: List[ReviewFinding] = []
        covered_rules = []
        omitted_rules = []

        if not bundle.specification:
            findings.append(ReviewFinding(
                severity="BLOCKER",
                rule_id=None,
                artifact="specification",
                version="0.1",
                location="bundle",
                description="Specification missing",
                evidence="specification is None",
                correction="Provide spec"
            ))
            return ReviewReport(
                status="INCOMPLETE",
                summary="Baseline v0.1 review incomplete: missing specification.",
                findings=findings,
                coverage=ReviewCoverage(len(bundle.source_requirements), [], [r.id for r in bundle.source_requirements], [], []),
                check_results=[{"check": "baseline_metadata", "status": "FAIL"}],
                provenance=ProvenanceRecord(reviewer_version="0.1.0", engine="naive_id_matching"),
                timestamp="2026-11-18T10:00:00Z",
                bundle_id=bundle.bundle_id,
            )

        spec_rule_ids = {r.rule_id for r in bundle.specification.rules}
        for req in bundle.source_requirements:
            if req.id in spec_rule_ids:
                covered_rules.append(req.id)
            else:
                omitted_rules.append(req.id)
                findings.append(ReviewFinding(
                    severity="BLOCKER",
                    rule_id=req.id,
                    artifact="specification",
                    version="0.1",
                    location="rules",
                    description=f"Rule {req.id} omitted in spec (baseline ID match)",
                    evidence=f"ID {req.id} not in spec",
                    correction=f"Add {req.id}"
                ))

        # Baseline ignores code AST and assumes code is correct if string exists
        # Baseline ignores boundary intervals (> vs >=)
        # Baseline cannot generate counterexamples

        status = "CHANGES_REQUIRED" if omitted_rules else "PASS"

        return ReviewReport(
            status=status,
            summary=f"Baseline v0.1 review complete: {len(covered_rules)} covered, {len(omitted_rules)} omitted.",
            findings=findings,
            coverage=ReviewCoverage(
                total_source_requirements=len(bundle.source_requirements),
                covered_requirements=covered_rules,
                omitted_requirements=omitted_rules,
                unreviewed_scope=["Python code AST execution", "Boundary intervals", "Precedence ordering"],
                unsupported_features=[],
            ),
            check_results=[{"check": "id_matching", "status": status}],
            provenance=ProvenanceRecord(reviewer_version="0.1.0", engine="naive_id_matching"),
            timestamp="2026-11-18T10:00:00Z",
            bundle_id=bundle.bundle_id,
        )
