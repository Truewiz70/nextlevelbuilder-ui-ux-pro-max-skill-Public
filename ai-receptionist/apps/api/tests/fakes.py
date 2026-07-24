"""In-memory fakes for the conversation module's external providers, used to
exercise the real database + retrieval logic in tests without live API keys.
"""

import re

from app.modules.conversation.providers.base import (
    CompletionRequest,
    CompletionResult,
    EmbeddingProvider,
    LLMProvider,
)


class FakeEmbeddingProvider(EmbeddingProvider):
    """Deterministic bag-of-words embedding — good enough to prove retrieval
    correctness (the relevant chunk ranks first) without a real embedding
    model. Consistent within one test process; not meant to match any real
    embedding space."""

    def __init__(self, dimensions: int = 1024) -> None:
        self._dim = dimensions

    async def embed(self, texts: list[str], *, for_query: bool = False) -> list[list[float]]:
        return [self._vectorize(t) for t in texts]

    def _vectorize(self, text: str) -> list[float]:
        vector = [0.0] * self._dim
        for word in re.findall(r"[a-z0-9]+", text.lower()):
            vector[hash(word) % self._dim] += 1.0
        norm = sum(v * v for v in vector) ** 0.5 or 1.0
        return [v / norm for v in vector]


class FakeLLMProvider(LLMProvider):
    def __init__(self, response_text: str = "This is a fake answer.") -> None:
        self.response_text = response_text
        self.calls: list[CompletionRequest] = []

    async def complete(self, request: CompletionRequest, *, fast: bool = False) -> CompletionResult:
        self.calls.append(request)
        return CompletionResult(
            text=self.response_text,
            tool_calls=[],
            input_tokens=10,
            output_tokens=5,
            model="fake-fast" if fast else "fake-primary",
        )


class RaisingLLMProvider(LLMProvider):
    """Simulates an API failure — used to prove tool dispatch degrades to a
    safe fallback instead of breaking the caller's turn."""

    async def complete(self, request: CompletionRequest, *, fast: bool = False) -> CompletionResult:
        raise RuntimeError("simulated LLM outage")
