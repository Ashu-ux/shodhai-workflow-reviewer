"""
Unified AI-Assisted Workflow Reviewer.
Coordinates Stage 1 (Effective Requirements), Stage 2 (Deterministic Semantic Verification),
and Stage 3 (Model Trust & Injection Defense) with caching and ablation controls.
"""

import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from src.contracts.models import (
    ReviewBundle,
    ReviewReport,
    ReviewFinding,
    ReviewCoverage,
    ProvenanceRecord,
)
from src.effective_requirements.engine import EffectiveRequirementsEngine
from src.checker.semantic_verifier import SemanticVerifier
from src.model.client_interface import ModelClient
from src.model.fake_client import FakeModelClient
from src.model.trust_validator import ModelTrustValidator, SYSTEM_REVIEWER_PROMPT


class WorkflowReviewer:
    """The central Reviewer application integrating deterministic and model-assisted analysis."""

    def __init__(
        self,
        model_client: Optional[ModelClient] = None,
        enable_cache: bool = True,
        ablate_python_ast: bool = False,
        ablate_precedence: bool = False,
    ):
        self.model_client = model_client or FakeModelClient(mode="normal")
        self.enable_cache = enable_cache
        self.ablate_python_ast = ablate_python_ast
        self.ablate_precedence = ablate_precedence
        self._cache: Dict[str, ReviewReport] = {}

    def review(self, bundle: ReviewBundle) -> ReviewReport:
        start_time = time.perf_counter()

        # 1. Compute Cache Key
        bundle_hash = self._compute_bundle_hash(bundle)
        cache_key = f"{bundle_hash}_ast_{not self.ablate_python_ast}_prec_{not self.ablate_precedence}"
        
        if self.enable_cache and cache_key in self._cache:
            cached_report = self._cache[cache_key]
            cached_report.provenance.cached = True
            return cached_report

        # 2. Stage 1: Derive Effective Requirements
        derivation = EffectiveRequirementsEngine.derive(
            source_requirements=bundle.source_requirements,
            approval_records=bundle.approval_records
        )

        # 3. Stage 2: Deterministic Semantic Verification
        # In ablation mode: temporarily alter bundle to simulate ablated behavior if specified
        active_bundle = bundle
        if self.ablate_python_ast and bundle.python_snippets:
            # Ablating AST checking: replace snippet code with dummy so AST checker doesn't inspect
            from copy import deepcopy
            active_bundle = deepcopy(bundle)
            active_bundle.python_snippets = []  # Disables code-level checks

        findings, coverage, check_results, deterministic_status = SemanticVerifier.verify(
            bundle=active_bundle,
            derivation=derivation
        )

        # 4. Stage 3: Model Review & Trust Validation
        user_prompt = json.dumps({
            "bundle_id": bundle.bundle_id,
            "source_requirements": [r.title for r in bundle.source_requirements],
            "spec_rules": [r.rule_id for r in bundle.specification.rules] if bundle.specification else [],
            "approval_count": len(bundle.approval_records),
        })

        model_response = self.model_client.generate_review(
            bundle_dict=bundle.to_dict(),
            system_prompt=SYSTEM_REVIEWER_PROMPT,
            user_prompt=user_prompt,
        )

        final_status, merged_findings, model_meta, provenance = ModelTrustValidator.validate_and_merge(
            bundle=bundle,
            deterministic_status=deterministic_status,
            deterministic_findings=findings,
            model_response=model_response,
        )

        # Build Summary
        blocker_count = sum(1 for f in merged_findings if f.severity == "BLOCKER")
        warning_count = sum(1 for f in merged_findings if f.severity == "WARNING")
        summary = (
            f"Review completed for bundle '{bundle.bundle_id}'. "
            f"Status: {final_status}. Blockers: {blocker_count}, Warnings: {warning_count}. "
            f"Coverage: {len(coverage.covered_requirements)}/{coverage.total_source_requirements} requirements covered."
        )

        total_elapsed = (time.perf_counter() - start_time) * 1000
        provenance.latency_ms = total_elapsed

        report = ReviewReport(
            status=final_status,
            summary=summary,
            findings=merged_findings,
            coverage=coverage,
            check_results=check_results,
            provenance=provenance,
            timestamp=datetime.now(timezone.utc).isoformat(),
            bundle_id=bundle.bundle_id,
        )

        if self.enable_cache:
            self._cache[cache_key] = report

        return report

    def _compute_bundle_hash(self, bundle: ReviewBundle) -> str:
        serialized = json.dumps(bundle.to_dict(), sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
