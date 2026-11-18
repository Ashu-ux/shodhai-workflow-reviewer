"""
Unified Deterministic Semantic Verifier.
Executes multi-artifact semantic checks, generates evidence-backed findings,
and produces concrete counterexamples for behavioral discrepancies.
"""

from typing import List, Dict, Optional, Any, Tuple
from src.contracts.models import (
    ReviewBundle,
    ReviewFinding,
    ReviewCoverage,
    Counterexample,
)
from src.effective_requirements.engine import DerivationResult, EffectiveRequirement
from src.dsl.parser import ConditionParser
from src.dsl.normalizer import ConditionNormalizer
from src.checker.graph_traversal import GraphTraversalAnalyzer
from src.checker.python_ast_checker import PythonASTChecker
from src.checker.precedence import PrecedenceAnalyzer
from src.checker.counterexample import CounterexampleGenerator


class SemanticVerifier:
    """Performs deterministic verification of decision workflows against effective requirements."""

    @classmethod
    def verify(
        cls,
        bundle: ReviewBundle,
        derivation: DerivationResult
    ) -> Tuple[List[ReviewFinding], ReviewCoverage, List[Dict[str, Any]], str]:
        findings: List[ReviewFinding] = []
        check_results: List[Dict[str, Any]] = []
        
        effective_map = derivation.effective_requirements
        ordered_effective = derivation.ordered_rules
        fallback_action = bundle.specification.fallback_action if bundle.specification else "normal_queue"

        covered_rules: List[str] = []
        omitted_rules: List[str] = []
        unreviewed_scope: List[str] = []
        unsupported_features: List[str] = [u["condition_dsl"] for u in derivation.unsupported_rules]

        # 1. Contradictory Approvals Check
        if derivation.contradictions:
            for c in derivation.contradictions:
                findings.append(ReviewFinding(
                    severity="WARNING",
                    rule_id=c["target_rule_id"],
                    artifact="approval_record",
                    version="1.0",
                    location=f"ApprovalRecords:{c['conflicting_records']}",
                    description=c["details"],
                    evidence=f"Conflicting approved changes for {c['target_rule_id']}.",
                    correction="Resolve conflicting approval records by withdrawing one or issuing an ordered superseding approval."
                ))
                unreviewed_scope.append(f"Rule {c['target_rule_id']} (unresolved contradictory approval records)")
            check_results.append({
                "check": "approval_consistency",
                "status": "WARN",
                "details": f"{len(derivation.contradictions)} contradictory approval record(s) found."
            })
        else:
            check_results.append({
                "check": "approval_consistency",
                "status": "PASS",
                "details": "No contradictory approval records detected."
            })

        # 2. Unsupported / Ambiguous Requirements Check
        if derivation.unsupported_rules:
            for u in derivation.unsupported_rules:
                findings.append(ReviewFinding(
                    severity="WARNING",
                    rule_id=u["rule_id"],
                    artifact="source_requirement",
                    version="1.0",
                    location=f"SourceRequirement:{u['rule_id']}",
                    description=f"Rule contains unsupported/ambiguous condition: {u['condition_dsl']}",
                    evidence=f"Reason: {u['reason']}",
                    correction="Refactor condition into supported DSL syntax (e.g. numeric intervals, equality, missing checks)."
                ))
                unreviewed_scope.append(f"Rule {u['rule_id']} ({u['condition_dsl']})")
            check_results.append({
                "check": "syntax_support",
                "status": "WARN",
                "details": f"{len(derivation.unsupported_rules)} requirement(s) contain unsupported syntax."
            })
        else:
            check_results.append({
                "check": "syntax_support",
                "status": "PASS",
                "details": "All requirements adhere to supported DSL grammar."
            })

        # 3. Missing Artifact Check
        if not bundle.specification:
            findings.append(ReviewFinding(
                severity="WARNING",
                rule_id=None,
                artifact="specification",
                version="1.0",
                location="bundle.specification",
                description="Specification artifact is missing from review bundle.",
                evidence="specification is None",
                correction="Provide the structured specification artifact."
            ))
        if not bundle.workflow_graph:
            findings.append(ReviewFinding(
                severity="WARNING",
                rule_id=None,
                artifact="workflow_graph",
                version="1.0",
                location="bundle.workflow_graph",
                description="Workflow graph artifact is missing from review bundle.",
                evidence="workflow_graph is None",
                correction="Provide the versioned workflow graph."
            ))
        if not bundle.python_snippets:
            findings.append(ReviewFinding(
                severity="WARNING",
                rule_id=None,
                artifact="python_snippet",
                version="1.0",
                location="bundle.python_snippets",
                description="Linked Python snippet artifact is missing from review bundle.",
                evidence="python_snippets list is empty",
                correction="Provide linked Python implementation snippet."
            ))

        # If essential artifacts are missing, terminate early with INCOMPLETE
        if not bundle.specification or not bundle.workflow_graph or not bundle.python_snippets:
            coverage = ReviewCoverage(
                total_source_requirements=len(bundle.source_requirements),
                covered_requirements=[],
                omitted_requirements=[r.id for r in bundle.source_requirements],
                unreviewed_scope=unreviewed_scope + ["Complete workflow and implementation verification"],
                unsupported_features=unsupported_features
            )
            return findings, coverage, check_results, "INCOMPLETE"

        # 4. Specification Review & Omission Check
        spec_rules_by_id = {r.rule_id: r for r in bundle.specification.rules}
        for req in ordered_effective:
            if req.rule_id not in spec_rules_by_id:
                omitted_rules.append(req.rule_id)
                findings.append(ReviewFinding(
                    severity="BLOCKER",
                    rule_id=req.rule_id,
                    artifact="specification",
                    version=bundle.specification.version,
                    location=f"Specification:{bundle.specification.id}",
                    description=f"Requirement '{req.rule_id}' is omitted from specification.",
                    evidence=f"Source requirement '{req.title}' ({req.condition_dsl} -> {req.action}) absent from spec rules.",
                    correction=f"Add rule '{req.rule_id}' to specification rules list."
                ))
            else:
                covered_rules.append(req.rule_id)
                spec_rule = spec_rules_by_id[req.rule_id]
                parsed_spec_cond = ConditionParser.parse(spec_rule.condition_dsl)
                
                # Check semantic condition equivalence
                if req.is_supported and not ConditionNormalizer.are_equivalent(req.parsed_ast, parsed_spec_cond):
                    findings.append(ReviewFinding(
                        severity="BLOCKER",
                        rule_id=req.rule_id,
                        artifact="specification",
                        version=bundle.specification.version,
                        location=f"Specification.rules[{req.rule_id}]",
                        description=f"Specification condition disagrees with effective requirement for '{req.rule_id}'.",
                        evidence=f"Effective condition: '{req.condition_dsl}', Specification condition: '{spec_rule.condition_dsl}'.",
                        correction=f"Update specification condition to '{req.condition_dsl}'."
                    ))

                # Check action agreement
                if spec_rule.action != req.action:
                    findings.append(ReviewFinding(
                        severity="BLOCKER",
                        rule_id=req.rule_id,
                        artifact="specification",
                        version=bundle.specification.version,
                        location=f"Specification.rules[{req.rule_id}].action",
                        description=f"Specification action '{spec_rule.action}' disagrees with requirement action '{req.action}'.",
                        evidence=f"Expected action: '{req.action}', found: '{spec_rule.action}'.",
                        correction=f"Update action in specification to '{req.action}'."
                    ))

        # Check for unapproved changes in specification
        for spec_rule in bundle.specification.rules:
            if spec_rule.rule_id not in effective_map:
                findings.append(ReviewFinding(
                    severity="BLOCKER",
                    rule_id=spec_rule.rule_id,
                    artifact="specification",
                    version=bundle.specification.version,
                    location=f"Specification.rules[{spec_rule.rule_id}]",
                    description=f"Specification contains unapproved rule '{spec_rule.rule_id}' not found in requirements.",
                    evidence=f"Rule '{spec_rule.rule_id}' has no corresponding source requirement or approved record.",
                    correction="Remove unapproved rule from specification or submit approval record."
                ))

        # 5. Workflow Graph Verification
        wf_analysis = GraphTraversalAnalyzer.analyze(bundle.workflow_graph)
        if not wf_analysis["is_valid"]:
            for err in wf_analysis["errors"]:
                findings.append(ReviewFinding(
                    severity="BLOCKER",
                    rule_id=None,
                    artifact="workflow_graph",
                    version=bundle.workflow_graph.version,
                    location=f"WorkflowGraph:{bundle.workflow_graph.id}",
                    description=err,
                    evidence=f"Workflow graph structural check failed: {err}",
                    correction="Fix graph transitions and ensure all condition branches are defined."
                ))
        for warn in wf_analysis["warnings"]:
            findings.append(ReviewFinding(
                severity="WARNING",
                rule_id=None,
                artifact="workflow_graph",
                version=bundle.workflow_graph.version,
                location=f"WorkflowGraph:{bundle.workflow_graph.id}",
                description=warn,
                evidence=warn,
                correction="Remove dead nodes or wire them into the traversal path."
            ))

        # Check graph nodes for rule coverage
        wf_nodes_by_rule = {n.rule_ref: n for n in bundle.workflow_graph.nodes.values() if n.rule_ref}
        for req in ordered_effective:
            if req.rule_id not in wf_nodes_by_rule:
                if req.rule_id not in omitted_rules:
                    omitted_rules.append(req.rule_id)
                findings.append(ReviewFinding(
                    severity="BLOCKER",
                    rule_id=req.rule_id,
                    artifact="workflow_graph",
                    version=bundle.workflow_graph.version,
                    location=f"WorkflowGraph:{bundle.workflow_graph.id}",
                    description=f"Requirement '{req.rule_id}' has no condition node in workflow graph.",
                    evidence=f"No workflow node with rule_ref='{req.rule_id}'.",
                    correction=f"Add decision node in workflow graph for rule '{req.rule_id}'."
                ))

        # 6. Python Snippet Verification & AST Inspection
        py_snippet = bundle.python_snippets[0]
        ast_result = PythonASTChecker.inspect_and_extract(py_snippet)
        
        if not ast_result["syntax_valid"] or not ast_result["is_safe"]:
            findings.append(ReviewFinding(
                severity="BLOCKER",
                rule_id=None,
                artifact="python_snippet",
                version=py_snippet.version,
                location=f"{py_snippet.file_path}:{py_snippet.entry_function}",
                description=ast_result["error"] or "Python AST verification failed",
                evidence=f"Code: {py_snippet.code[:100]}...",
                correction="Ensure code is valid, syntax-correct, and strictly within restricted Python subset."
            ))

        # 7. Precedence Verification
        expected_rule_order = [r.rule_id for r in ordered_effective]
        # Extract workflow evaluation order from reachable graph paths
        actual_wf_order: List[str] = []
        for path in wf_analysis.get("terminal_paths", []):
            for step in path:
                node_id = step[0]
                if node_id in bundle.workflow_graph.nodes:
                    ref = bundle.workflow_graph.nodes[node_id].rule_ref
                    if ref and ref not in actual_wf_order:
                        actual_wf_order.append(ref)

        order_mismatches = PrecedenceAnalyzer.analyze_order_agreement(expected_rule_order, actual_wf_order)
        for mismatch in order_mismatches:
            findings.append(ReviewFinding(
                severity="BLOCKER",
                rule_id=mismatch["higher_priority_rule"],
                artifact="workflow_graph",
                version=bundle.workflow_graph.version,
                location=f"WorkflowGraph:Precedence",
                description=mismatch["description"],
                evidence=f"Workflow evaluated {mismatch['lower_priority_rule']} before {mismatch['higher_priority_rule']}.",
                correction=f"Rewire graph so {mismatch['higher_priority_rule']} is evaluated before {mismatch['lower_priority_rule']}."
            ))

        # 8. Counterexample Generation for Behavioral Discrepancies
        # Build actual implementation simulator from Python AST or Workflow
        def actual_evaluator(ticket: Dict[str, Any]) -> str:
            if ast_result["is_safe"] and ast_result["branches"]:
                return PythonASTChecker.evaluate_safely(
                    ast_result["branches"],
                    ast_result["fallback_action"] or fallback_action,
                    ticket
                )
            # Fallback to specification simulator
            for rule in bundle.specification.rules:
                cond_ast = ConditionParser.parse(rule.condition_dsl)
                if cond_ast.evaluate(ticket):
                    return rule.action
            return fallback_action

        # Search for concrete counterexample
        cex = CounterexampleGenerator.search_counterexample(
            effective_rules=ordered_effective,
            effective_fallback=fallback_action,
            actual_evaluator_fn=actual_evaluator,
        )

        if cex:
            # Check if any blocker finding can attach this counterexample
            attached = False
            for f in findings:
                if f.severity == "BLOCKER" and (f.rule_id == cex.violating_rule or not f.rule_id):
                    f.counterexample = cex.to_dict()
                    attached = True
                    break
            if not attached:
                # Add behavioral divergence finding
                findings.append(ReviewFinding(
                    severity="BLOCKER",
                    rule_id=cex.violating_rule,
                    artifact="python_snippet",
                    version=py_snippet.version,
                    location=f"{py_snippet.file_path}:{py_snippet.entry_function}",
                    description=f"Behavioral discrepancy between effective requirements and actual implementation.",
                    evidence=cex.evidence,
                    counterexample=cex.to_dict(),
                    correction="Align Python implementation thresholds and logic with effective requirements."
                ))

        # Check coverage
        coverage = ReviewCoverage(
            total_source_requirements=len(bundle.source_requirements),
            covered_requirements=sorted(list(set(covered_rules))),
            omitted_requirements=sorted(list(set(omitted_rules))),
            unreviewed_scope=unreviewed_scope,
            unsupported_features=unsupported_features,
        )

        # Status determination:
        # PASS: Complete review of effective requirements within declared supported scope, no blocker.
        # CHANGES_REQUIRED: Evidenced blocker exists.
        # INCOMPLETE: Missing evidence, ambiguity, contradictory approvals without blocker, or failure prevents full review.
        has_blocker = any(f.severity == "BLOCKER" for f in findings)
        if has_blocker:
            status = "CHANGES_REQUIRED"
        elif derivation.unsupported_rules or unreviewed_scope:
            status = "INCOMPLETE"
        elif len(covered_rules) < len(ordered_effective):
            status = "CHANGES_REQUIRED"
        else:
            status = "PASS"

        return findings, coverage, check_results, status
