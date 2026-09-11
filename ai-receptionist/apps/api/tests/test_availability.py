"""Availability maths. No database, no calendar — these are the rules that
decide what a caller is offered, and the ones that break subtly in
production: timezone handling, closing-time boundaries, and DST.
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.modules.scheduling.availability import (
    available_slots,
    describe_slots,
    generate_candidate_slots,
    overlaps,
    subtract_busy,
)
from app.modules.scheduling.providers.base import TimeSlot

NY = ZoneInfo("America/New_York")
WEEKDAY_9_TO_5 = {
    "mon": [["09:00", "17:00"]],
    "tue": [["09:00", "17:00"]],
    "wed": [["09:00", "17:00"]],
    "thu": [["09:00", "17:00"]],
    "fri": [["09:00", "17:00"]],
}


def _ny(year, month, day, hour, minute=0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=NY).astimezone(UTC)


def test_slots_fall_inside_local_business_hours_not_utc_hours() -> None:
    """The classic bug: treating '09:00' as UTC. In New York in September
    that is 5am local — five hours before the practice opens."""
    # Tuesday 2026-09-15.
    slots = generate_candidate_slots(
        business_hours=WEEKDAY_9_TO_5,
        timezone="America/New_York",
        window_start=_ny(2026, 9, 15, 0),
        window_end=_ny(2026, 9, 16, 0),
        duration_minutes=60,
        now=_ny(2026, 9, 14, 12),
    )
    assert slots
    local_hours = {s.start.astimezone(NY).hour for s in slots}
    assert min(local_hours) == 9
    # A 60-minute slot cannot start at 5pm; the last valid start is 4pm.
    assert max(local_hours) == 16


def test_slot_must_fit_entirely_before_closing() -> None:
    """A 90-minute appointment at 4pm would run to 5:30pm — past close — and
    must not be offered even though 4pm itself is within opening hours."""
    slots = generate_candidate_slots(
        business_hours=WEEKDAY_9_TO_5,
        timezone="America/New_York",
        window_start=_ny(2026, 9, 15, 0),
        window_end=_ny(2026, 9, 16, 0),
        duration_minutes=90,
        now=_ny(2026, 9, 14, 12),
    )
    latest = max(s.end for s in slots)
    assert latest == _ny(2026, 9, 15, 17)
    assert all(s.end <= _ny(2026, 9, 15, 17) for s in slots)


def test_closed_days_produce_no_slots() -> None:
    # 2026-09-19 is a Saturday; WEEKDAY_9_TO_5 has no weekend entry.
    slots = generate_candidate_slots(
        business_hours=WEEKDAY_9_TO_5,
        timezone="America/New_York",
        window_start=_ny(2026, 9, 19, 0),
        window_end=_ny(2026, 9, 20, 0),
        duration_minutes=30,
        now=_ny(2026, 9, 18, 12),
    )
    assert slots == []


def test_minimum_notice_excludes_imminent_slots() -> None:
    """A caller at 9:05am must not be offered 9:15am when the practice needs
    two hours' notice."""
    now = _ny(2026, 9, 15, 9, 5)
    slots = generate_candidate_slots(
        business_hours=WEEKDAY_9_TO_5,
        timezone="America/New_York",
        window_start=now,
        window_end=_ny(2026, 9, 16, 0),
        duration_minutes=30,
        now=now,
        min_notice_hours=2,
    )
    assert slots
    assert min(s.start for s in slots) >= now + timedelta(hours=2)


def test_slots_never_start_in_the_past() -> None:
    now = _ny(2026, 9, 15, 13, 37)
    slots = generate_candidate_slots(
        business_hours=WEEKDAY_9_TO_5,
        timezone="America/New_York",
        window_start=_ny(2026, 9, 15, 0),
        window_end=_ny(2026, 9, 16, 0),
        duration_minutes=30,
        now=now,
    )
    assert all(s.start >= now for s in slots)


def test_dst_transition_keeps_local_opening_hours() -> None:
    """US DST ends Sunday 2026-11-01. Monday the 2nd is UTC-5 where Friday
    the 30th was UTC-4 — the practice still opens at 9am local both days,
    which is a different UTC hour. Anything that stores the offset rather
    than the zone gets this wrong."""
    before = generate_candidate_slots(
        business_hours=WEEKDAY_9_TO_5,
        timezone="America/New_York",
        window_start=_ny(2026, 10, 30, 0),
        window_end=_ny(2026, 10, 31, 0),
        duration_minutes=60,
        now=_ny(2026, 10, 29, 12),
    )
    after = generate_candidate_slots(
        business_hours=WEEKDAY_9_TO_5,
        timezone="America/New_York",
        window_start=_ny(2026, 11, 2, 0),
        window_end=_ny(2026, 11, 3, 0),
        duration_minutes=60,
        now=_ny(2026, 11, 1, 12),
    )
    assert min(s.start.astimezone(NY).hour for s in before) == 9
    assert min(s.start.astimezone(NY).hour for s in after) == 9
    # ...and the UTC hours genuinely differ, so the test isn't vacuous.
    assert min(s.start.hour for s in before) != min(s.start.hour for s in after)


def test_back_to_back_appointments_remain_bookable() -> None:
    """Half-open intervals: a slot ending exactly when a busy period begins
    is not a conflict. Treating it as one loses an appointment per boundary."""
    slot = TimeSlot(start=_ny(2026, 9, 15, 9), end=_ny(2026, 9, 15, 10))
    adjacent_after = TimeSlot(start=_ny(2026, 9, 15, 10), end=_ny(2026, 9, 15, 11))
    adjacent_before = TimeSlot(start=_ny(2026, 9, 15, 8), end=_ny(2026, 9, 15, 9))
    genuine_overlap = TimeSlot(start=_ny(2026, 9, 15, 9, 30), end=_ny(2026, 9, 15, 10, 30))

    assert not overlaps(slot, adjacent_after)
    assert not overlaps(slot, adjacent_before)
    assert overlaps(slot, genuine_overlap)


def test_busy_periods_remove_only_conflicting_slots() -> None:
    slots = [
        TimeSlot(start=_ny(2026, 9, 15, 9), end=_ny(2026, 9, 15, 10)),
        TimeSlot(start=_ny(2026, 9, 15, 10), end=_ny(2026, 9, 15, 11)),
        TimeSlot(start=_ny(2026, 9, 15, 11), end=_ny(2026, 9, 15, 12)),
    ]
    busy = [TimeSlot(start=_ny(2026, 9, 15, 10, 15), end=_ny(2026, 9, 15, 10, 45))]
    remaining = subtract_busy(slots, busy)
    assert [s.start for s in remaining] == [_ny(2026, 9, 15, 9), _ny(2026, 9, 15, 11)]


def test_available_slots_excludes_calendar_conflicts() -> None:
    busy = [TimeSlot(start=_ny(2026, 9, 15, 9), end=_ny(2026, 9, 15, 12))]
    slots = available_slots(
        business_hours=WEEKDAY_9_TO_5,
        timezone="America/New_York",
        window_start=_ny(2026, 9, 15, 0),
        window_end=_ny(2026, 9, 16, 0),
        duration_minutes=60,
        busy_periods=busy,
        now=_ny(2026, 9, 14, 12),
    )
    assert slots
    assert min(s.start.astimezone(NY).hour for s in slots) == 12


def test_describe_slots_is_speakable() -> None:
    """The string is read aloud by the voice agent, so no ISO timestamps and
    no 24-hour clock."""
    slots = [
        TimeSlot(start=_ny(2026, 9, 15, 9), end=_ny(2026, 9, 15, 10)),
        TimeSlot(start=_ny(2026, 9, 15, 14, 30), end=_ny(2026, 9, 15, 15, 30)),
        TimeSlot(start=_ny(2026, 9, 16, 12), end=_ny(2026, 9, 16, 13)),
    ]
    spoken = describe_slots(slots, "America/New_York", limit=3)
    assert spoken == "Tuesday at 9 am, Tuesday at 2:30 pm, or Wednesday at 12 pm"
    assert "T" not in spoken.replace("Tuesday", "").replace("Wednesday", "")


def test_describe_slots_single_slot_has_no_conjunction() -> None:
    slots = [TimeSlot(start=_ny(2026, 9, 15, 9), end=_ny(2026, 9, 15, 10))]
    assert describe_slots(slots, "America/New_York") == "Tuesday at 9 am"


def test_describe_slots_empty_is_empty_string() -> None:
    assert describe_slots([], "America/New_York") == ""


def test_zero_duration_and_inverted_window_are_rejected() -> None:
    common = {
        "business_hours": WEEKDAY_9_TO_5,
        "timezone": "America/New_York",
        "now": _ny(2026, 9, 14, 12),
    }
    assert (
        generate_candidate_slots(
            window_start=_ny(2026, 9, 15, 0),
            window_end=_ny(2026, 9, 16, 0),
            duration_minutes=0,
            **common,
        )
        == []
    )
    assert (
        generate_candidate_slots(
            window_start=_ny(2026, 9, 16, 0),
            window_end=_ny(2026, 9, 15, 0),
            duration_minutes=30,
            **common,
        )
        == []
    )
