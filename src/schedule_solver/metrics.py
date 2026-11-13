"""Observable metrics, shared by both scheduling algorithms."""

from collections import defaultdict
from zoneinfo import ZoneInfo

from .models import Meeting, Metrics, Result, Workload


def result_for(
    work: Workload, meetings: list[Meeting], seconds: float, algorithm: str
) -> Result:
    by_day = defaultdict(list)
    loads = dict.fromkeys((p.id for p in work.people), 0)
    people = {p.id: p for p in work.people}
    requests = {r.id: r for r in work.requests}
    for meeting in meetings:
        duration = requests[meeting.request_id].duration_minutes
        for attendee in meeting.attendees:
            day = meeting.start.astimezone(ZoneInfo(people[attendee].timezone)).date()
            by_day[attendee, day].append(meeting)
            loads[attendee] += duration
    gaps = 0
    for group in by_day.values():
        span = (
            max(m.end for m in group) - min(m.start for m in group)
        ).total_seconds() // 60
        occupied = sum(requests[m.request_id].duration_minutes for m in group)
        gaps += int(span) - occupied
    scheduled = {m.request_id for m in meetings}
    return Result(
        algorithm=algorithm,
        meetings=sorted(meetings, key=lambda m: (m.start, m.request_id)),
        unscheduled=[r.id for r in work.requests if r.id not in scheduled],
        metrics=Metrics(
            meetings_scheduled=len(meetings),
            priority_scheduled=sum(requests[m.request_id].priority for m in meetings),
            gap_minutes=gaps,
            active_person_days=len(by_day),
            load_spread_minutes=max(loads.values()) - min(loads.values()),
            solve_seconds=seconds,
        ),
    )
