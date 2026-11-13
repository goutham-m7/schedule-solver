"""Validate schedule assignments independently of solver objective metadata."""

from collections import Counter, defaultdict
from datetime import timedelta
from zoneinfo import ZoneInfo

from .calendars import eligible, legal_starts, overlaps
from .models import Period, Result, Workload


def validate_schedule(work: Workload, result: Result):
    requests = {r.id: r for r in work.requests}
    people = {p.id: p for p in work.people}
    seen, occupied = set(), defaultdict(list)
    counts, loads = Counter(), Counter()
    for meeting in result.meetings:
        if meeting.request_id in seen or meeting.request_id not in requests:
            raise ValueError("schedule request IDs must be unique and known")
        seen.add(meeting.request_id)
        r = requests[meeting.request_id]
        Period(start=meeting.start, end=meeting.end)
        minute = (meeting.start - work.start).total_seconds() / 60
        if (
            minute % work.grid_minutes
            or (meeting.end - meeting.start).total_seconds() != r.duration_minutes * 60
        ):
            raise ValueError("meeting must match request duration and start grid")
        team = meeting.attendees
        if (
            not team
            or len(team) != len(set(team))
            or set(team) - people.keys()
            or not set(r.required_attendees) <= set(team)
        ):
            raise ValueError(
                "meeting needs unique known attendees and all required people"
            )
        for attr in ("skills", "roles"):
            for name, count in getattr(r, attr).items():
                if sum(name in getattr(people[pid], attr) for pid in team) < count:
                    raise ValueError("meeting does not cover staffing requirements")
        for pid in team:
            p = people[pid]
            if not eligible(p, r) or int(
                minute
            ) // work.grid_minutes not in legal_starts(work, r, p):
                raise ValueError("meeting violates eligibility or calendar constraints")
            before = meeting.start - timedelta(minutes=p.buffer_before_minutes)
            after = meeting.end + timedelta(minutes=p.buffer_after_minutes)
            if any(overlaps(before, after, a, b) for a, b in occupied[pid]):
                raise ValueError(
                    "meeting overlaps another attendee's buffered assignment"
                )
            occupied[pid].append((before, after))
            day = meeting.start.astimezone(ZoneInfo(p.timezone)).date()
            counts[pid, day] += 1
            if counts[pid, day] > p.max_meetings_per_day:
                raise ValueError("meeting exceeds local daily cap")
            loads[pid] += r.duration_minutes
    if work.max_load_difference_minutes is not None:
        values = [loads[p.id] for p in work.people]
        if max(values) - min(values) > work.max_load_difference_minutes:
            raise ValueError("schedule violates hard load fairness")
