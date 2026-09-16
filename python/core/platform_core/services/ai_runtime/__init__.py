"""AI runtime provider skeleton (Stage 1 — no live model calls)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class AiGenerationRequest:
    business_id: UUID
    prompt: str
    correlation_id: str


@dataclass(frozen=True)
class AiGenerationResult:
    content: str
    provider: str
    fallback_used: bool = False


class AiRuntimeProvider(ABC):
    """Abstract AI runtime contract for Stage 2+ generation flows."""

    provider_id: str

    @abstractmethod
    async def generate(self, request: AiGenerationRequest) -> AiGenerationResult:
        raise NotImplementedError


class StubAiRuntimeProvider(AiRuntimeProvider):
    """Stage 1 placeholder — deterministic fallback only."""

    provider_id = "stub"

    async def generate(self, request: AiGenerationRequest) -> AiGenerationResult:
        return AiGenerationResult(
            content="",
            provider=self.provider_id,
            fallback_used=True,
        )
