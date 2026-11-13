"""Input-order, earliest-fit baseline with greedy skill coverage; no CP-SAT calls."""

from collections import Counter
from datetime import timedelta
from time import perf_counter
from zoneinfo import ZoneInfo

from .calendars import eligible, legal_starts, overlaps, padded, slots
from .metrics import result_for
from .models import Meeting, Workload


def greedy(work: Workload):
    begun = perf_counter()
    meetings = []
    counts, loads = Counter(), Counter()
    for request in work.requests:
        legal = {
            p.id: set(legal_starts(work, request, p))
            for p in work.people
            if eligible(p, request)
        }
        for slot in slots(work, request):
            start = work.instant(slot * work.grid_minutes)
            available = []
            for p in work.people:
                if slot not in legal.get(p.id, set()):
                    continue
                day = start.astimezone(ZoneInfo(p.timezone)).date()
                if counts[p.id, day] >= p.max_meetings_per_day:
                    continue
                if any(
                    p.id in m.attendees
                    and overlaps(
                        *padded(work, request, p, slot),
                        m.start - timedelta(minutes=p.buffer_before_minutes),
                        m.end + timedelta(minutes=p.buffer_after_minutes),
                    )
                    for m in meetings
                ):
                    continue
                available.append(p)
            by_id = {p.id: p for p in available}
            if not set(request.required_attendees) <= by_id.keys():
                continue
            team = list(request.required_attendees)

            def deficits(by_id=by_id, team=team, request=request):
                return [
                    (
                        attr,
                        name,
                        max(
                            0,
                            count
                            - sum(name in getattr(by_id[pid], attr) for pid in team),
                        ),
                    )
                    for attr in ("skills", "roles")
                    for name, count in getattr(request, attr).items()
                ]

            while any(count for _, _, count in deficits()):
                candidates = [
                    (
                        sum(
                            count > 0 and name in getattr(p, attr)
                            for attr, name, count in deficits()
                        ),
                        p.id,
                    )
                    for p in available
                    if p.id not in team
                ]
                if not candidates or max(score for score, _ in candidates) == 0:
                    break
                # Stable input order is a fair first-fit tie-break, not future knowledge.
                score = max(score for score, _ in candidates)
                team.append(next(pid for value, pid in candidates if value == score))
            if any(count for _, _, count in deficits()):
                continue
            team.extend(
                pid
                for pid in request.optional_attendees
                if pid in by_id and pid not in team
            )
            new_loads = [
                loads[p.id] + (request.duration_minutes if p.id in team else 0)
                for p in work.people
            ]
            if (
                work.max_load_difference_minutes is not None
                and max(new_loads) - min(new_loads) > work.max_load_difference_minutes
            ):
                continue
            meetings.append(
                Meeting(
                    request_id=request.id,
                    start=start,
                    end=start + timedelta(minutes=request.duration_minutes),
                    attendees=team,
                )
            )
            for pid in team:
                counts[pid, start.astimezone(ZoneInfo(by_id[pid].timezone)).date()] += 1
                loads[pid] += request.duration_minutes
            break
    return result_for(work, meetings, perf_counter() - begun, "greedy-first-fit")
