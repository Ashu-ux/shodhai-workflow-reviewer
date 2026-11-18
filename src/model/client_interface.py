"""
Model Client Interface and Response Protocol.
Defines contracts for interacting with language models and capturing provenance.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class ModelResponse:
    raw_content: str
    model_name: str
    mode: str = "normal"
    latency_ms: float = 0.0
    token_usage: Dict[str, int] = field(default_factory=dict)
    retries: int = 0
    is_error: bool = False
    error_message: Optional[str] = None
    prompt_hash: Optional[str] = None
    response_hash: Optional[str] = None


class ModelClient(ABC):
    """Abstract interface for reviewer model clients."""

    @abstractmethod
    def generate_review(
        self,
        bundle_dict: Dict[str, Any],
        system_prompt: str,
        user_prompt: str,
    ) -> ModelResponse:
        """Sends review context and prompts to model and returns ModelResponse."""
        pass
