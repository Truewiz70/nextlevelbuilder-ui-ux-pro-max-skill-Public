# tenants

**Purpose:** Tenant identity and configuration: number → tenant resolution,
versioned agent configs, and assembly of the runtime `AgentDefinition`
(system prompt with guardrails, greeting, voice) that the voice vendor runs.

**Dependencies:** `core` (db, config). Exposes types consumed by `telephony`.

**Inputs:** inbound phone numbers (E.164), tenant/agent rows seeded via
`scripts/seed_demo.py` (dashboard CRUD lands in Phase 7).
**Outputs:** `Tenant`, `PhoneNumber`, `AgentConfig` models; `AgentDefinition`.

**Configuration:** none beyond `core` settings; per-tenant behavior lives in
the database (see `config/tenants/*.yaml` for the documented surface).

**Security note:** number resolution runs before tenant identity exists, so
`phone_numbers` carries a SELECT-only RLS policy permitting lookup from
unscoped sessions (migration 0002). No other table is readable unscoped.

**Future improvements:** tenant CRUD API + onboarding flow; prompt templating
per vertical; config validation against a JSON schema.

**Known risks:** prompt assembly is deliberately simple (persona + guardrails
+ escalation); qualification-flow injection into the prompt arrives with the
conversation engine in Phase 4.
