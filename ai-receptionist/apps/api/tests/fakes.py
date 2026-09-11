"""In-memory fakes for the conversation module's external providers, used to
exercise the real database + retrieval logic in tests without live API keys.
"""

import hashlib
import re
import uuid
from datetime import datetime

from app.modules.conversation.providers.base import (
    CompletionRequest,
    CompletionResult,
    EmbeddingProvider,
    LLMProvider,
)
from app.modules.notifications.providers.base import EmailProvider, SMSProvider
from app.modules.scheduling.providers.base import (
    BookingRequest,
    BookingResult,
    CalendarProvider,
    TimeSlot,
)


class FakeEmbeddingProvider(EmbeddingProvider):
    """Deterministic bag-of-words embedding — good enough to prove retrieval
    correctness (the relevant chunk ranks first) without a real embedding
    model. Not meant to match any real embedding space.

    Buckets come from a stable digest rather than the builtin `hash()`:
    Python randomizes string hashing per process, so `hash()` would give a
    different bucket layout on every run and make distance-threshold
    assertions pass or fail at random.
    """

    def __init__(self, dimensions: int = 1024) -> None:
        self._dim = dimensions

    async def embed(self, texts: list[str], *, for_query: bool = False) -> list[list[float]]:
        return [self._vectorize(t) for t in texts]

    def _vectorize(self, text: str) -> list[float]:
        vector = [0.0] * self._dim
        for word in re.findall(r"[a-z0-9]+", text.lower()):
            vector[self._bucket(word)] += 1.0
        norm = sum(v * v for v in vector) ** 0.5 or 1.0
        return [v / norm for v in vector]

    def _bucket(self, word: str) -> int:
        digest = hashlib.blake2b(word.encode(), digest_size=8).digest()
        return int.from_bytes(digest, "big") % self._dim


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


class FakeCalendarProvider(CalendarProvider):
    """In-memory calendar. Records every booking so tests can assert how many
    times the vendor was actually written to — the thing that matters when
    proving idempotency and release-on-failure."""

    def __init__(self, busy: list[TimeSlot] | None = None) -> None:
        self.busy = list(busy or [])
        self.booked: list[BookingRequest] = []
        self.cancelled: list[str] = []
        self.fail_booking: Exception | None = None
        self.fail_busy: Exception | None = None

    async def list_busy_periods(
        self, tenant_id: uuid.UUID, window_start: datetime, window_end: datetime
    ) -> list[TimeSlot]:
        if self.fail_busy:
            raise self.fail_busy
        return [b for b in self.busy if b.end > window_start and b.start < window_end]

    async def book(self, request: BookingRequest) -> BookingResult:
        if self.fail_booking:
            raise self.fail_booking
        self.booked.append(request)
        return BookingResult(
            external_event_id=f"evt-{len(self.booked)}", slot=request.slot, confirmed=True
        )

    async def cancel(self, tenant_id: uuid.UUID, external_event_id: str) -> None:
        self.cancelled.append(external_event_id)


class FakeEmailProvider(EmailProvider):
    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []
        self.fail: Exception | None = None

    async def send(
        self, *, to: str, subject: str, html: str, from_address: str, idempotency_key: str
    ) -> str:
        if self.fail:
            raise self.fail
        self.sent.append({"to": to, "subject": subject, "html": html, "key": idempotency_key})
        return f"email-{len(self.sent)}"


class FakeSMSProvider(SMSProvider):
    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []
        self.fail: Exception | None = None

    async def send(self, *, to: str, body: str, idempotency_key: str) -> str:
        if self.fail:
            raise self.fail
        self.sent.append({"to": to, "body": body, "key": idempotency_key})
        return f"sms-{len(self.sent)}"
