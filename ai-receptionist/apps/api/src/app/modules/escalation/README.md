# escalation

**Purpose:** The v1 escalation path — voicemail-plus-callback. Every
escalation trigger (caller asks for a human, out-of-scope question, distress)
becomes a `callback_requests` row for the dashboard's callback queue. There
is no live transfer in v1 (Phase 1 product decision).

**Dependencies:** `core` (db). Called from `conversation.tools.ToolExecutor`
(the `request_callback` tool) and, later, the post-call worker for missed
calls.

**Inputs:** caller, reason, optional preferred window / voicemail transcript.
**Outputs:** a `callback_requests` row (open → contacted → resolved).

**Configuration:** none beyond `core`; escalation triggers and the callback
promise live in the tenant's `agent_configs.escalation_policy`.

**Future improvements:** SLA timers / overdue-callback alerts; optional live
transfer as a v2 escalation mode behind the same trigger set.

**Known risks:** none specific at this stage — the module is a thin, typed
write path over one table.
