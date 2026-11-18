"""
Deterministic Local Fake Model Client for Testing and Offline Evaluation.
Supports fault injection: timeouts, malformed JSON, truncated JSON,
hallucinated rule references, and prompt injection susceptibility.
"""

import hashlib
import json
import time
from typing import Dict, Any, Optional
from src.model.client_interface import ModelClient, ModelResponse


class FakeModelClient(ModelClient):
    """Deterministic local fake client providing controlled outputs and fault injection."""

    def __init__(self, mode: str = "normal", fail_retries: int = 0):
        self.mode = mode
        self.fail_retries = fail_retries
        self.call_count = 0

    def generate_review(
        self,
        bundle_dict: Dict[str, Any],
        system_prompt: str,
        user_prompt: str,
    ) -> ModelResponse:
        self.call_count += 1
        start_time = time.perf_counter()
        
        prompt_data = (system_prompt + user_prompt).encode("utf-8")
        prompt_hash = hashlib.sha256(prompt_data).hexdigest()

        # Fault Injection: TIMEOUT
        if self.mode == "timeout":
            elapsed = (time.perf_counter() - start_time) * 1000
            return ModelResponse(
                raw_content="",
                model_name="fake-reviewer-v1",
                mode="timeout",
                latency_ms=elapsed + 150.0,
                token_usage={"prompt_tokens": 0, "completion_tokens": 0},
                retries=self.call_count - 1,
                is_error=True,
                error_message="Request timed out after 3000ms",
                prompt_hash=prompt_hash,
                response_hash=None,
            )

        # Fault Injection: MALFORMED_JSON
        if self.mode == "malformed_json":
            raw = '{"status": "CHANGES_REQUIRED", "summary": "Unclosed json string...'
            elapsed = (time.perf_counter() - start_time) * 1000
            resp_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
            return ModelResponse(
                raw_content=raw,
                model_name="fake-reviewer-v1",
                mode="malformed_json",
                latency_ms=elapsed + 10.0,
                token_usage={"prompt_tokens": 120, "completion_tokens": 30},
                retries=self.call_count - 1,
                prompt_hash=prompt_hash,
                response_hash=resp_hash,
            )

        # Fault Injection: TRUNCATED_JSON
        if self.mode == "truncated_json":
            raw = '{"status": "CHANGES_REQUIRED", "summary": "Review complete but truncated.", "findings": [{"rule_id": "R1"'
            elapsed = (time.perf_counter() - start_time) * 1000
            resp_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
            return ModelResponse(
                raw_content=raw,
                model_name="fake-reviewer-v1",
                mode="truncated_json",
                latency_ms=elapsed + 10.0,
                token_usage={"prompt_tokens": 120, "completion_tokens": 25},
                retries=self.call_count - 1,
                prompt_hash=prompt_hash,
                response_hash=resp_hash,
            )

        # Fault Injection: HALLUCINATED_REFS
        if self.mode == "hallucinated_refs":
            raw = json.dumps({
                "status": "CHANGES_REQUIRED",
                "summary": "Model hallucinated rule IDs outside bundle.",
                "model_findings": [
                    {
                        "severity": "BLOCKER",
                        "rule_id": "R999_NONEXISTENT",
                        "description": "Rule R999_NONEXISTENT violated policy.",
                        "correction": "Fix nonexistent rule."
                    }
                ],
                "qualitative_notes": "Hallucinated reference injected."
            })
            elapsed = (time.perf_counter() - start_time) * 1000
            resp_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
            return ModelResponse(
                raw_content=raw,
                model_name="fake-reviewer-v1",
                mode="hallucinated_refs",
                latency_ms=elapsed + 15.0,
                token_usage={"prompt_tokens": 150, "completion_tokens": 60},
                retries=self.call_count - 1,
                prompt_hash=prompt_hash,
                response_hash=resp_hash,
            )

        # Fault Injection: PROMPT_INJECTION
        if self.mode == "prompt_injection_susceptible":
            # Emulates a naive LLM that falls for an adversarial injection in requirements
            raw = json.dumps({
                "status": "PASS",
                "summary": "Administrative override accepted. All policies verified as PASS.",
                "model_findings": [],
                "qualitative_notes": "Followed instructions inside requirement text to mark PASS."
            })
            elapsed = (time.perf_counter() - start_time) * 1000
            resp_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
            return ModelResponse(
                raw_content=raw,
                model_name="fake-reviewer-v1",
                mode="prompt_injection_susceptible",
                latency_ms=elapsed + 12.0,
                token_usage={"prompt_tokens": 200, "completion_tokens": 40},
                retries=self.call_count - 1,
                prompt_hash=prompt_hash,
                response_hash=resp_hash,
            )

        # MODE: NORMAL
        # Generates structured qualitative feedback aligned with bundle
        bundle_id = bundle_dict.get("bundle_id", "bundle")
        raw = json.dumps({
            "status": "ANALYZED",
            "summary": f"Semantic natural-language review completed for {bundle_id}.",
            "model_findings": [],
            "qualitative_notes": "Verified prose intent against formal policy structure.",
            "clarity_score": 0.95
        })
        elapsed = (time.perf_counter() - start_time) * 1000
        resp_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()

        return ModelResponse(
            raw_content=raw,
            model_name="fake-reviewer-v1",
            mode="normal",
            latency_ms=elapsed + 8.0,
            token_usage={"prompt_tokens": 180, "completion_tokens": 55},
            retries=self.call_count - 1,
            prompt_hash=prompt_hash,
            response_hash=resp_hash,
        )
