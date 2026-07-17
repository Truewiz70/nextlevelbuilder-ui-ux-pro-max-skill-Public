"""Integration test: the full M1 call lifecycle through the real stack.

Drives the actual webhook endpoint (signature check included) against a live
Postgres + Redis: call started → progress event → end-of-call report, then
asserts the call row, transcript, and post-call job. Skipped automatically
when the services aren't reachable (unit CI still passes); the pipeline CI
runs it against its service containers.
"""

import json
import socket
import uuid
from pathlib import Path

import pytest
import redis as sync_redis
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.core.config import Settings
from app.core.queue import POST_CALL_QUEUE
from app.main import create_app

FIXTURES = Path(__file__).parent / "fixtures"
SECRET = "test-secret"


def _reachable(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


requires_services = pytest.mark.skipif(
    not (_reachable("localhost", 5432) and _reachable("localhost", 6379)),
    reason="requires local Postgres and Redis",
)


def _fixture(name: str, number: str, call_id: str) -> dict:
    raw = (FIXTURES / name).read_text()
    return json.loads(raw.replace("+15550100001", number).replace("vapi-call-0001", call_id))


@requires_services
def test_full_call_lifecycle() -> None:
    settings = Settings(_env_file=None, app_env="test", vapi_webhook_secret=SECRET)
    sync_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    engine = create_engine(sync_url)
    redis = sync_redis.Redis.from_url(settings.redis_url)

    tenant_id = uuid.uuid4()
    number = f"+1999{uuid.uuid4().int % 10**7:07d}"
    vendor_call_id = f"itest-{uuid.uuid4().hex[:12]}"

    # Seed a tenant + inbound number (phone_numbers is RLS-scoped).
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO tenants (id, slug, name, vertical) VALUES (:id, :slug, :n, 'dental')"
            ),
            {"id": str(tenant_id), "slug": f"flow-test-{tenant_id.hex[:8]}", "n": "Flow Test"},
        )
        conn.execute(
            text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": str(tenant_id)}
        )
        conn.execute(
            text("INSERT INTO phone_numbers (tenant_id, e164) VALUES (:tid, :e164)"),
            {"tid": str(tenant_id), "e164": number},
        )

    try:
        app = create_app(settings)
        with TestClient(app) as client:

            def post(fixture_name: str):
                body = json.dumps(_fixture(fixture_name, number, vendor_call_id))
                return client.post(
                    "/webhooks/voice/vapi", content=body, headers={"x-vapi-secret": SECRET}
                )

            # Unsigned requests are rejected at the edge.
            unsigned = client.post("/webhooks/voice/vapi", content="{}")
            assert unsigned.status_code == 401

            assert post("vapi_call_started.json").json() == {"status": "accepted"}
            assert post("vapi_tool_calls.json").json() == {"status": "accepted"}
            assert post("vapi_end_of_call_report.json").json() == {"status": "accepted"}

        with engine.begin() as conn:
            conn.execute(
                text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": str(tenant_id)}
            )
            call = conn.execute(
                text(
                    "SELECT id, ended_at, recording_url, vendor_cost_cents FROM calls "
                    "WHERE vendor_call_id = :vcid"
                ),
                {"vcid": vendor_call_id},
            ).one()
            assert call.ended_at is not None
            assert call.recording_url.endswith(".wav")
            assert call.vendor_cost_cents == 37

            turns = conn.execute(
                text("SELECT turns FROM transcripts WHERE call_id = :cid"), {"cid": call.id}
            ).scalar_one()
            assert [t["role"] for t in turns] == ["assistant", "caller", "assistant"]
            assert "new patients" in turns[1]["text"]

            event_types = {
                row.event_type
                for row in conn.execute(
                    text("SELECT event_type FROM call_events WHERE call_id = :cid"),
                    {"cid": call.id},
                )
            }
            assert {"tool_call", "call_ended"} <= event_types

        # The finished call was handed to the async post-call queue.
        jobs = [json.loads(item) for item in redis.lrange(POST_CALL_QUEUE, 0, -1)]
        ours = [j for j in jobs if j.get("call_id") == str(call.id)]
        assert len(ours) == 1
    finally:
        for item in redis.lrange(POST_CALL_QUEUE, 0, -1):
            if vendor_call_id in item.decode() or str(tenant_id) in item.decode():
                redis.lrem(POST_CALL_QUEUE, 0, item)
        with engine.begin() as conn:
            # FK cascades bypass RLS, so deleting the tenant removes all children.
            conn.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": str(tenant_id)})
        engine.dispose()
        redis.close()
