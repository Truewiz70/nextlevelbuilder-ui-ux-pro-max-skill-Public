"""CRMProvider — CRM backends (HubSpot first; Pipedrive/Zoho as follow-ons).

CRM writes happen on the async post-call path only (never while the caller
waits) and are retried with backoff. Field mapping per tenant lives in the
crm module; this interface moves normalized contacts and deals.
"""

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ContactRecord:
    phone: str
    name: str | None = None
    email: str | None = None
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DealRecord:
    contact_external_id: str
    title: str
    stage: str
    properties: dict[str, Any] = field(default_factory=dict)


class CRMProvider(ABC):
    @abstractmethod
    async def upsert_contact(self, tenant_id: uuid.UUID, contact: ContactRecord) -> str:
        """Create or update by phone/email; return the external contact id."""

    @abstractmethod
    async def create_deal(self, tenant_id: uuid.UUID, deal: DealRecord) -> str: ...

    @abstractmethod
    async def log_activity(
        self, tenant_id: uuid.UUID, contact_external_id: str, summary: str
    ) -> None:
        """Attach a call summary to the contact's timeline."""
