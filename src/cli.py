"""
Command Line Interface (CLI) for AI-Assisted Workflow Reviewer.
Provides single-command invocation for offline evaluation, individual bundle review,
baseline checkpoint comparison, and ablation studies.
"""

import sys
import os
import argparse
import json
from src.contracts.models import ReviewBundle
from src.reviewer import WorkflowReviewer
from evaluation.run_eval import run_full_evaluation
from evaluation.compare_checkpoint import run_checkpoint_comparison, load_all_bundles
from evaluation.run_ablation import run_controlled_ablation


def main():
    parser = argparse.ArgumentParser(
        prog="shodhai-reviewer",
        description="ShodhAI AI-Assisted Workflow Reviewer CLI"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Command: evaluate
    eval_parser = subparsers.add_parser("evaluate", help="Run full offline evaluation over review bundles")
    eval_parser.add_argument("--bundles-dir", default=None, help="Directory containing JSON review bundles")
    eval_parser.add_argument("--reports-dir", default=None, help="Directory to save output JSON reports")

    # Command: review
    review_parser = subparsers.add_parser("review", help="Review an individual bundle file")
    review_parser.add_argument("bundle_path", help="Path to JSON review bundle file")
    review_parser.add_argument("--ablate-ast", action="store_true", help="Ablate Python AST verification")

    # Command: compare
    compare_parser = subparsers.add_parser("compare", help="Compare Baseline (v0.1) vs Final (v1.0)")
    compare_parser.add_argument("--bundles-dir", default=None, help="Directory containing JSON review bundles")

    # Command: ablate
    ablate_parser = subparsers.add_parser("ablate", help="Run controlled ablation experiment")
    ablate_parser.add_argument("--bundles-dir", default=None, help="Directory containing JSON review bundles")

    # Command: test
    test_parser = subparsers.add_parser("test", help="Run offline test suite and regression checks")

    args = parser.parse_args()

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    default_bundles_dir = os.path.join(project_root, "bundles")
    default_reports_dir = os.path.join(project_root, "reports")

    if args.command == "evaluate" or args.command is None:
        b_dir = args.bundles_dir or default_bundles_dir
        r_dir = getattr(args, "reports_dir", None) or default_reports_dir
        run_full_evaluation(b_dir, r_dir)

    elif args.command == "review":
        if not os.path.exists(args.bundle_path):
            print(f"Error: Bundle file '{args.bundle_path}' not found.", file=sys.stderr)
            sys.exit(1)
        with open(args.bundle_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        bundle = ReviewBundle.from_dict(data)
        reviewer = WorkflowReviewer(ablate_python_ast=args.ablate_ast)
        report = reviewer.review(bundle)
        print(report.to_json(indent=2))

    elif args.command == "compare":
        b_dir = args.bundles_dir or default_bundles_dir
        bundles = load_all_bundles(b_dir)
        results = run_checkpoint_comparison(bundles)
        print(json.dumps(results, indent=2))

    elif args.command == "ablate":
        b_dir = args.bundles_dir or default_bundles_dir
        bundles = load_all_bundles(b_dir)
        results = run_controlled_ablation(bundles)
        print(json.dumps(results, indent=2))

    elif args.command == "test":
        import unittest
        loader = unittest.TestLoader()
        suite = loader.discover(os.path.join(project_root, "tests"))
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
