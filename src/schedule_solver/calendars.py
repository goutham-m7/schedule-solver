"""UTC grid and strict ICS busy-calendar import. All intervals are half-open."""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from icalendar import Calendar

from .models import Period, Person, Request, Workload


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


def import_ics(text: str, local_timezone: str) -> list[Period]:
    """Read explicit VEVENT busy blocks; recurrence/floating events fail closed."""
    zone = ZoneInfo(local_timezone)
    try:
        calendar = Calendar.from_ical(text)
    except Exception as exc:
        raise ValueError(f"invalid ICS: {exc}") from exc
    if calendar.name != "VCALENDAR":
        raise ValueError("ICS must contain VCALENDAR")
    periods = []
    for event in calendar.walk("VEVENT"):
        if any(
            key in event
            for key in ("RRULE", "RDATE", "EXDATE", "RECURRENCE-ID", "EXRULE")
        ):
            raise ValueError(
                "recurrence is not supported; expand recurring events before import"
            )
        if (
            str(event.get("STATUS", "")).upper() == "CANCELLED"
            or str(event.get("TRANSP", "")).upper() == "TRANSPARENT"
        ):
            continue
        if "DTSTART" not in event:
            raise ValueError("VEVENT requires DTSTART")
        start = event.decoded("DTSTART")
        if "DTEND" in event and "DURATION" in event:
            raise ValueError("VEVENT cannot specify both DTEND and DURATION")
        if "DTEND" in event:
            end = event.decoded("DTEND")
        elif "DURATION" in event:
            end = start + event.decoded("DURATION")
        elif type(start) is date:
            end = start + timedelta(days=1)
        else:
            raise ValueError("timed VEVENT requires DTEND or DURATION")
        if isinstance(start, datetime) != isinstance(end, datetime):
            raise ValueError("DTSTART and DTEND must have the same value type")

        def aware(value):
            if isinstance(value, datetime):
                if value.tzinfo is None:
                    raise ValueError("floating ICS timestamps are not supported")
                return value.astimezone(UTC)
            return datetime.combine(value, time(), zone).astimezone(UTC)

        periods.append(Period(start=aware(start), end=aware(end)))
    return merge_periods(periods)
