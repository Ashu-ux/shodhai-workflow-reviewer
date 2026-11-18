"""
Single CPU-Only Offline Evaluation Runner.
Executes the full evaluation suite, baseline comparison, and controlled ablation,
generating machine-readable JSON reports in reports/ and displaying a console summary.
"""

import os
import sys
import glob
import json
import time
from typing import List
from src.contracts.models import ReviewBundle, ReviewReport
from src.reviewer import WorkflowReviewer
from evaluation.metrics import MetricsCalculator
from evaluation.compare_checkpoint import run_checkpoint_comparison
from evaluation.run_ablation import run_controlled_ablation


def load_bundles(bundle_dir: str) -> List[ReviewBundle]:
    bundles = []
    files = sorted(glob.glob(os.path.join(bundle_dir, "*.json")))
    for fpath in files:
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
            bundles.append(ReviewBundle.from_dict(data))
    return bundles


def run_full_evaluation(bundle_dir: str, reports_dir: str):
    start_total = time.perf_counter()
    os.makedirs(reports_dir, exist_ok=True)
    bundles = load_bundles(bundle_dir)

    print("=" * 80)
    print(" SHODHAI TAKE-HOME: AI-ASSISTED WORKFLOW REVIEWER EVALUATION")
    print(f" Loaded {len(bundles)} review bundles from: {bundle_dir}")
    print(" Execution Mode: CPU-only offline reproducible sandbox")
    print("=" * 80)

    # 1. Run Final Reviewer (v1.0)
    reviewer = WorkflowReviewer(enable_cache=False)
    reports: List[ReviewReport] = []

    print("\n[Stage 1-3] Running Unified Semantic Verification across all bundles...")
    for idx, b in enumerate(bundles, start=1):
        rep = reviewer.review(b)
        reports.append(rep)
        match_icon = "[PASS]" if rep.status == b.expected_status else "[MISMATCH]"
        frozen_tag = " (FROZEN)" if b.is_frozen else ""
        print(f"  {idx:02d}. {b.bundle_id[:40]:<40} Expected: {b.expected_status:<16} Actual: {rep.status:<16} {match_icon}{frozen_tag}")

    metrics = MetricsCalculator.calculate(bundles, reports)

    # Save evaluation_results.json
    eval_results_path = os.path.join(reports_dir, "evaluation_results.json")
    with open(eval_results_path, "w", encoding="utf-8") as f:
        json.dump({
            "metrics": metrics,
            "individual_reports": [r.to_dict() for r in reports]
        }, f, indent=2)

    # 2. Run Baseline vs Final Checkpoint Comparison
    print("\n[Stage 4] Running Checkpoint Comparison (v0.1 Baseline vs v1.0 Final)...")
    comparison_results = run_checkpoint_comparison(bundles)
    comparison_path = os.path.join(reports_dir, "baseline_vs_final.json")
    with open(comparison_path, "w", encoding="utf-8") as f:
        json.dump(comparison_results, f, indent=2)

    # 3. Run Controlled Ablation Experiment
    print("[Stage 4] Running Controlled Ablation (Ablating Python AST Code Verification)...")
    ablation_results = run_controlled_ablation(bundles)
    ablation_path = os.path.join(reports_dir, "ablation_results.json")
    with open(ablation_path, "w", encoding="utf-8") as f:
        json.dump(ablation_results, f, indent=2)

    # 4. Save Resource Usage Report
    resource_path = os.path.join(reports_dir, "resource_usage.json")
    with open(resource_path, "w", encoding="utf-8") as f:
        json.dump(metrics["resource_use"], f, indent=2)

    total_time = (time.perf_counter() - start_total) * 1000

    # Print Summary Table
    print("\n" + "=" * 80)
    print(" EVALUATION RESULTS SUMMARY")
    print("=" * 80)
    print(f" Total Bundles Evaluated:            {metrics['summary']['total_cases']}")
    print(f" Correct Decisions:                  {metrics['summary']['correct_decisions']} / {metrics['summary']['total_cases']} ({metrics['summary']['accuracy'] * 100:.1f}%)")
    print(f" False Passes (Defective -> PASS):    {metrics['decision_correctness']['false_passes']} / {metrics['decision_correctness']['total_defective_cases']} ({metrics['decision_correctness']['false_pass_rate'] * 100:.1f}%)")
    print(f" False Blocks (Valid -> BLOCK):      {metrics['decision_correctness']['false_blocks']} / {metrics['decision_correctness']['total_valid_cases']} ({metrics['decision_correctness']['false_block_rate'] * 100:.1f}%)")
    print(f" Counterexamples Generated:          {metrics['finding_quality']['concrete_counterexamples_generated']} / {metrics['finding_quality']['behavioral_mismatches_analyzed']} ({metrics['finding_quality']['counterexample_coverage_rate'] * 100:.1f}%)")
    print(f" Hallucinated Findings Admitted:     {metrics['finding_quality']['unsupported_findings_admitted']}")
    print("-" * 80)
    print(" CHECKPOINT COMPARISON (Baseline v0.1 vs Final v1.0):")
    v0_acc = comparison_results["full_suite_comparison"]["v0_baseline"]["summary"]["accuracy"] * 100
    v1_acc = comparison_results["full_suite_comparison"]["v1_final"]["summary"]["accuracy"] * 100
    print(f"   Baseline v0.1 Full Accuracy:      {v0_acc:.1f}% (False Passes: {comparison_results['full_suite_comparison']['v0_baseline']['decision_correctness']['false_passes']})")
    print(f"   Final v1.0 Full Accuracy:         {v1_acc:.1f}% (False Passes: {comparison_results['full_suite_comparison']['v1_final']['decision_correctness']['false_passes']})")
    print(f"   Frozen Set Accuracy (v1.0):       {comparison_results['frozen_set_comparison']['v1_final_accuracy'] * 100:.1f}%")
    print("-" * 80)
    print(" CONTROLLED ABLATION (Disabling Python AST Verification):")
    c_acc = ablation_results["control_metrics"]["summary"]["accuracy"] * 100
    a_acc = ablation_results["ablated_metrics"]["summary"]["accuracy"] * 100
    print(f"   Control Reviewer Accuracy:        {c_acc:.1f}%")
    print(f"   Ablated Reviewer Accuracy:        {a_acc:.1f}%")
    print(f"   Ablation Divergence:              {len(ablation_results['outcome_divergences'])} bundle(s) flipped to False Pass")
    print("-" * 80)
    print(f" Total Runtime:                      {total_time:.2f} ms")
    print(f" Machine-readable reports saved to:  {os.path.abspath(reports_dir)}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    b_dir = os.path.join(base_dir, "bundles")
    r_dir = os.path.join(base_dir, "reports")
    run_full_evaluation(b_dir, r_dir)
