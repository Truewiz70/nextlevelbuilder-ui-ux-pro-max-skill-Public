# scheduling

**Purpose:** Find open appointment times and book them, without ever selling
the same slot twice. Owns availability policy (business hours, service
durations, notice periods), the `appointments` write path, and the conflict
prevention that makes concurrent callers safe. Calendar vendors sit behind
`CalendarProvider` and are replaceable.

**Dependencies:** `core` (db, config, logging, security, queue),
`tenants` (the `Tenant` row supplies timezone, business hours, and the
`settings.scheduling` policy block). Called from
`conversation.tools.ToolExecutor` via the `check_availability` and
`book_appointment` tools. Enqueues onto `queue:confirmations`, which the
`notifications` module consumes — it does not call that module directly.

**Inputs:** a tenant, a requested service, an optional preferred time (ISO
8601 in the practice's local time), and the caller's name/phone/optional
email.
**Outputs:** spoken-language strings for the voice agent; an `appointments`
row; a calendar event; a queued confirmation job.

## The double-booking guarantee

This is the part worth understanding before changing anything here.

No calendar API offers an atomic "create this event only if the slot is
free". Two callers can pass an availability check milliseconds apart and both
try to book. So the calendar cannot be the arbiter — our own database is.
The serialization point is a partial unique index (migration 0005):

```sql
CREATE UNIQUE INDEX appointments_no_double_booking
    ON appointments (tenant_id, starts_at) WHERE status = 'confirmed';
```

`service.book_appointment` therefore runs in this order, and the order is the
design:

1. **Insert the appointment row.** This is the lock. The loser of a race gets
   a unique violation and is offered alternatives.
2. **Write to the calendar,** only once the slot is held.
3. **Release the reservation** if that write fails, so a vendor outage does
   not leave the slot phantom-booked.

Doing it the other way round (calendar first) cannot be serialized. Skipping
step 3 is how "ghost" appointments appear — held in our table, absent from
the practice's calendar.

Because the index is partial on `status = 'confirmed'`, cancelling an
appointment frees the slot immediately with no extra bookkeeping.

## Idempotency

A second unique index on `idempotency_key` distinguishes a *retry* from a
*race*. Both collide on the same slot, but only a retry carries a key we have
already seen — so a redelivered webhook returns the original appointment
while a genuine second caller is told the time is taken. Keys are scoped to
the call and the slot (`call:<id>:<iso-start>`); without a call id there is
no retry identity, so the key is made unique per attempt instead (keying on
the slot alone would let one caller be booked into another's appointment).

## Hot path

`check_availability` and `book_appointment` run while the caller is waiting,
inside the <2s tool budget (Phase 1 §3.3). Calendar HTTP calls carry a 5s
timeout, and every failure mode degrades to something a receptionist would
plausibly say rather than an error — a calendar outage becomes "let me take
your details and have someone call you back" (Phase 1 Risk R9).

**Configuration:** per-tenant, in `tenants.settings.scheduling`:

```yaml
scheduling:
  services:
    - { name: "Cleaning & check-up", duration_minutes: 60 }
    - { name: "Emergency exam", duration_minutes: 30 }
  min_notice_hours: 2
```

Service matching is deliberately loose — callers say "a cleaning", not
"Cleaning & check-up" — and falls back to the first configured service rather
than refusing. Business hours and timezone come from the `tenants` row.
Google credentials are per-tenant rows in `integrations`, Fernet-encrypted
with `CREDENTIALS_ENCRYPTION_KEY`, which lives only in the environment.

**Future improvements:** rescheduling and cancellation as in-call tools
(the provider already supports `cancel`); Cal.com as a second adapter;
per-provider/per-room resources rather than one calendar per tenant;
buffer time between appointments; waitlists when the horizon is full.

**Known risks:**
- The Google adapter is contract-tested against a mock transport, not live
  Google (`tests/test_google_calendar.py`). The wire format is locked down but
  unverified against the real API until the M3 live-booking test.
- Availability reads the calendar on every check. At high call volume this
  will need a short-lived cache, which reintroduces staleness — the DB-side
  conflict check in step 1 is what keeps that safe.
- `(tenant_id, starts_at)` assumes one bookable resource per tenant. A
  practice with two chairs needs the index widened to include a resource id,
  or it will under-book.
