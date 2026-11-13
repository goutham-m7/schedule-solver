"""UTC grid and strict ICS busy-calendar import. All intervals are half-open."""

import json
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

from icalendar import Calendar, Event

from .models import Period, Person, Request, Result, Workload
from .recurrence import event_periods


def eligible(person, request):
    return (
        person.id in request.required_attendees + request.optional_attendees
        or bool(person.skills & request.skills.keys())
        or bool(person.roles & request.roles.keys())
    )


def candidates_for(work: Workload, request: Request) -> list[Person]:
    """Remove provably unnecessary specialists before building interval variables.

    If requirement A's holders are a subset of B's, and A asks for at least
    as many people, satisfying A implies B. A B-only person can be removed
    without harming feasibility and strictly improves the staffing objective.
    Hard fairness disables this reduction: extra staff can then be necessary.
    """
    if work.max_load_difference_minutes is not None:
        return [p for p in work.people if eligible(p, request)]
    requirements = [
        (count, {p.id for p in work.people if name in getattr(p, attr)})
        for attr in ("skills", "roles")
        for name, count in sorted(getattr(request, attr).items())
    ]
    needed = set(request.required_attendees + request.optional_attendees)
    for i, (count, holders) in enumerate(requirements):
        redundant = any(
            other <= holders and n >= count and (other != holders or n > count or j < i)
            for j, (n, other) in enumerate(requirements)
            if j != i
        )
        if not redundant:
            needed.update(holders)
    return [p for p in work.people if p.id in needed]


def overlaps(a: datetime, b: datetime, c: datetime, d: datetime) -> bool:
    return a < d and c < b


def slots(work: Workload, request: Request) -> range:
    return range(
        max(0, (work.minutes - request.duration_minutes) // work.grid_minutes + 1)
    )


def padded(work: Workload, request: Request, person: Person, slot: int):
    start = work.instant(slot * work.grid_minutes)
    return (
        start - timedelta(minutes=person.buffer_before_minutes),
        start
        + timedelta(minutes=request.duration_minutes + person.buffer_after_minutes),
    )


def static_reasons(
    work: Workload, request: Request, person: Person, slot: int
) -> set[str]:
    start = work.instant(slot * work.grid_minutes)
    end = start + timedelta(minutes=request.duration_minutes)
    before, after = padded(work, request, person, slot)
    reasons = set()
    if start < request.earliest or end > request.latest:
        reasons.add(f"window:{request.id}")
    # Contiguous free periods are merged: a boundary between them is not busy time.
    free = merge_periods(person.availability)
    if not any(p.start <= before and after <= p.end for p in free) or any(
        overlaps(before, after, p.start, p.end) for p in person.busy
    ):
        reasons.add(f"availability:{person.id}")
    local_start, local_end = (
        before.astimezone(ZoneInfo(person.timezone)),
        after.astimezone(ZoneInfo(person.timezone)),
    )
    hours = person.working_hours
    if (
        local_start.date() != local_end.date()
        or local_start.weekday() not in hours.weekdays
        or local_start.time().replace(tzinfo=None) < hours.start
        or local_end.time().replace(tzinfo=None) > hours.end
    ):
        reasons.add(f"working_hours:{person.id}")
    return reasons


def legal_starts(work: Workload, request: Request, person: Person) -> list[int]:
    return [
        s for s in slots(work, request) if not static_reasons(work, request, person, s)
    ]


def merge_periods(periods: list[Period]) -> list[Period]:
    merged = []
    for period in sorted(periods, key=lambda p: p.start):
        if merged and period.start <= merged[-1].end:
            merged[-1] = Period(
                start=merged[-1].start, end=max(merged[-1].end, period.end)
            )
        else:
            merged.append(period)
    return merged


def import_ics(
    text: str,
    local_timezone: str,
    horizon: Period | None = None,
    *,
    max_occurrences: int = 10000,
) -> list[Period]:
    """Read busy blocks, expanding recurrence only inside an explicit horizon."""
    zone = ZoneInfo(local_timezone)
    if not 1 <= max_occurrences <= 10000:
        raise ValueError("max_occurrences must be between 1 and 10000")
    try:
        calendar = Calendar.from_ical(text)
    except Exception as exc:
        raise ValueError(f"invalid ICS: {exc}") from exc
    if calendar.name != "VCALENDAR":
        raise ValueError("ICS must contain VCALENDAR")
    periods = []
    for event in calendar.walk("VEVENT"):
        if event.errors:
            raise ValueError(
                f"invalid ICS recurrence or event property: {event.errors}"
            )
        if any(key in event for key in ("RECURRENCE-ID", "EXRULE")):
            raise ValueError("unsupported recurrence override or EXRULE")
        if (
            str(event.get("STATUS", "")).upper() == "CANCELLED"
            or str(event.get("TRANSP", "")).upper() == "TRANSPARENT"
        ):
            continue
        periods.extend(event_periods(event, zone, horizon, max_occurrences))
    return merge_periods(periods)


def export_ics(work: Workload, result: Result) -> str:
    """Serialize checked assignments; attendee IDs are not invented email addresses."""
    from .validation import validate_schedule

    validate_schedule(work, result)
    calendar = Calendar()
    calendar.add("prodid", "-//schedule-solver//EN")
    calendar.add("version", "2.0")
    stamp = datetime.now(UTC)
    for meeting in sorted(result.meetings, key=lambda m: (m.start, m.request_id)):
        event = Event()
        event.add(
            "uid",
            f"{uuid5(NAMESPACE_URL, 'schedule-solver:' + meeting.request_id)}@schedule-solver",
        )
        event.add("dtstamp", stamp)
        event.add("dtstart", meeting.start.astimezone(UTC))
        event.add("dtend", meeting.end.astimezone(UTC))
        event.add("summary", meeting.request_id)
        event.add(
            "x-schedule-attendees",
            json.dumps(sorted(meeting.attendees), ensure_ascii=False),
        )
        calendar.add_component(event)
    return calendar.to_ical().decode("utf-8")
