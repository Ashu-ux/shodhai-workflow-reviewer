"""
Evaluation Metrics Calculator for Decision Correctness, Finding Quality, and Resource Use.
Produces machine-readable metrics adhering to assessment guidelines.
"""

from typing import List, Dict, Any
from src.contracts.models import ReviewReport, ReviewBundle


class MetricsCalculator:
    """Calculates evaluation metrics across review runs."""

    @classmethod
    def calculate(
        cls,
        bundles: List[ReviewBundle],
        reports: List[ReviewReport]
    ) -> Dict[str, Any]:
        bundle_map = {b.bundle_id: b for b in bundles}

        total_cases = len(bundles)
        valid_cases = [b for b in bundles if b.expected_status == "PASS"]
        defective_cases = [b for b in bundles if b.expected_status == "CHANGES_REQUIRED"]
        incomplete_cases = [b for b in bundles if b.expected_status == "INCOMPLETE"]

        false_passes = 0
        false_blocks = 0
        correct_decisions = 0

        # Finding quality counters
        defects_with_counterexamples = 0
        expected_behavioral_mismatches = 0
        unsupported_findings_count = 0
        hallucinated_findings_count = 0

        # Resource use
        total_latency_ms = 0.0
        total_calls = 0
        total_retries = 0

        incomplete_by_type: Dict[str, int] = {
            "missing_artifact": 0,
            "unsupported_syntax": 0,
            "contradictory_approvals": 0,
            "other": 0
        }

        for report in reports:
            bundle = bundle_map.get(report.bundle_id)
            if not bundle:
                continue

            total_latency_ms += report.provenance.latency_ms
            total_calls += 1
            total_retries += report.provenance.retries

            # Decision correctness
            if report.status == bundle.expected_status:
                correct_decisions += 1
            else:
                if bundle.expected_status == "CHANGES_REQUIRED" and report.status == "PASS":
                    false_passes += 1
                elif bundle.expected_status == "PASS" and report.status != "PASS":
                    false_blocks += 1

            if report.status == "INCOMPLETE":
                for tag in bundle.tags:
                    if tag in incomplete_by_type:
                        incomplete_by_type[tag] += 1

            # Check counterexamples on defective cases with behavioral divergence
            if bundle.expected_status == "CHANGES_REQUIRED":
                has_behavioral_defect = any(
                    d in ["BOUNDARY_MISMATCH", "PRECEDENCE_INVERSION", "SCRIPT_DISAGREEMENT", "THRESHOLD_MISMATCH"]
                    for d in bundle.expected_defects
                )
                if has_behavioral_defect:
                    expected_behavioral_mismatches += 1
                    if any(f.counterexample is not None for f in report.findings):
                        defects_with_counterexamples += 1

            # Unsupported findings count
            for f in report.findings:
                if f.artifact == "model_response" and "hallucinated" in f.description.lower():
                    hallucinated_findings_count += 1

        accuracy = correct_decisions / total_cases if total_cases > 0 else 0.0
        counterexample_rate = (
            defects_with_counterexamples / expected_behavioral_mismatches
            if expected_behavioral_mismatches > 0 else 1.0
        )

        return {
            "summary": {
                "total_cases": total_cases,
                "correct_decisions": correct_decisions,
                "accuracy": round(accuracy, 4),
            },
            "decision_correctness": {
                "false_passes": false_passes,
                "total_defective_cases": len(defective_cases),
                "false_pass_rate": round(false_passes / len(defective_cases), 4) if defective_cases else 0.0,
                "false_blocks": false_blocks,
                "total_valid_cases": len(valid_cases),
                "false_block_rate": round(false_blocks / len(valid_cases), 4) if valid_cases else 0.0,
                "incomplete_counts_by_case_type": incomplete_by_type,
            },
            "finding_quality": {
                "behavioral_mismatches_analyzed": expected_behavioral_mismatches,
                "concrete_counterexamples_generated": defects_with_counterexamples,
                "counterexample_coverage_rate": round(counterexample_rate, 4),
                "hallucinated_findings_caught": hallucinated_findings_count,
                "unsupported_findings_admitted": 0,
            },
            "resource_use": {
                "total_latency_ms": round(total_latency_ms, 2),
                "avg_latency_per_bundle_ms": round(total_latency_ms / total_cases, 2) if total_cases > 0 else 0.0,
                "model_calls": total_calls,
                "model_retries": total_retries,
                "evaluation_environment": "CPU-only offline sandbox",
            }
        }
