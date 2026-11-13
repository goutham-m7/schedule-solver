"""Optional-interval CP-SAT model with explicit lexicographic optimization."""

from collections import defaultdict
from time import perf_counter
from zoneinfo import ZoneInfo

from ortools.sat.python import cp_model

from .calendars import candidates_for, eligible, legal_starts, slots
from .greedy import greedy
from .metrics import result_for
from .models import Meeting, ObjectivePass, Period, Workload


def solve(
    work: Workload, time_limit: float = 10.0, *, previous: list[Meeting] | None = None
):
    """Bound each optimization pass by a fifth of time_limit; return honest statuses.

    Model construction and explanations are not included in CP search's time limit.
    A timed-out pass with no incumbent preserves the preceding pass's solution.
    """
    if not 0 < time_limit <= 120:
        raise ValueError("time_limit must be in (0, 120] seconds")
    if previous is not None:
        validate_previous(work, previous)
    begun = perf_counter()
    warm_start = greedy(work)
    warm_meetings = {m.request_id: m for m in warm_start.meetings}
    model = cp_model.CpModel()
    present, starts, attendance = {}, {}, {}
    intervals, daily = defaultdict(list), defaultdict(list)
    optional, unnecessary = [], []
    all_bools = []
    for r in work.requests:
        y = present[r.id] = model.new_bool_var(f"scheduled:{r.id}")
        all_bools.append(y)
        available_slots = slots(work, r)
        if not available_slots:
            model.add(y == 0)
        start = starts[r.id] = model.new_int_var(
            0, max(0, len(available_slots) - 1), f"start:{r.id}"
        )
        # Canonical absent start removes a large symmetry without constraining present meetings.
        model.add(start == 0).only_enforce_if(y.Not())
        candidates = {}
        pool = (
            [p for p in work.people if eligible(p, r)]
            if previous is not None
            else candidates_for(work, r)
        )
        for p in pool:
            legal = legal_starts(work, r, p)
            if not legal:
                continue
            a = attendance[r.id, p.id] = model.new_bool_var(f"attend:{r.id}:{p.id}")
            all_bools.append(a)
            candidates[p.id] = a
            model.add(a <= y)
            model.add_linear_expression_in_domain(
                start, cp_model.Domain.from_values(legal)
            ).only_enforce_if(a)
            interval = model.new_optional_fixed_size_interval_var(
                start * work.grid_minutes - p.buffer_before_minutes,
                r.duration_minutes + p.buffer_before_minutes + p.buffer_after_minutes,
                a,
                f"interval:{r.id}:{p.id}",
            )
            intervals[p.id].append(interval)
            zone = ZoneInfo(p.timezone)
            by_date = defaultdict(list)
            for slot in legal:
                day = (
                    work.instant(slot * work.grid_minutes)
                    .astimezone(zone)
                    .date()
                    .isoformat()
                )
                by_date[day].append(slot)
            membership = []
            for day, day_slots in sorted(by_date.items()):
                # A one-day horizon needs no table encoding or extra presence variable.
                on_day = (
                    a
                    if len(by_date) == 1
                    else model.new_bool_var(f"day:{r.id}:{p.id}:{day}")
                )
                if len(by_date) > 1:
                    model.add_linear_expression_in_domain(
                        start, cp_model.Domain.from_values(day_slots)
                    ).only_enforce_if(on_day)
                    membership.append(on_day)
                daily[p.id, day].append((r, start, on_day))
            if membership:
                model.add(sum(membership) == a)
            if p.id in r.optional_attendees:
                optional.append(a)
            elif p.id not in r.required_attendees:
                unnecessary.append(a)
        for person_id in r.required_attendees:
            model.add(candidates.get(person_id, 0) == y)
        for attr in ("skills", "roles"):
            for skill, count in getattr(r, attr).items():
                model.add(
                    sum(
                        candidates[p.id]
                        for p in work.people
                        if p.id in candidates and skill in getattr(p, attr)
                    )
                    >= count * y
                )
        model.add(sum(candidates.values()) >= y)
    for group in intervals.values():
        model.add_no_overlap(group)
    gaps, active_days = [], []
    people = {p.id: p for p in work.people}
    for (pid, day), entries in daily.items():
        model.add(sum(a for _, _, a in entries) <= people[pid].max_meetings_per_day)
        active = model.new_bool_var(f"active:{pid}:{day}")
        count = sum(a for _, _, a in entries)
        model.add(count >= active)
        model.add(count <= len(entries) * active)
        first_candidates, last_candidates = [], []
        for r, start, a in entries:
            f = model.new_int_var(0, work.minutes, "first_candidate")
            e = model.new_int_var(0, work.minutes, "last_candidate")
            model.add(f == start * work.grid_minutes).only_enforce_if(a)
            model.add(f == work.minutes).only_enforce_if(a.Not())
            model.add(
                e == start * work.grid_minutes + r.duration_minutes
            ).only_enforce_if(a)
            model.add(e == 0).only_enforce_if(a.Not())
            first_candidates.append(f)
            last_candidates.append(e)
        first = model.new_int_var(0, work.minutes, "first")
        last = model.new_int_var(0, work.minutes, "last")
        model.add_min_equality(first, first_candidates)
        model.add_max_equality(last, last_candidates)
        gaps.append(
            last
            - first
            + work.minutes * (1 - active)
            - sum(r.duration_minutes * a for r, _, a in entries)
        )
        # Implied by NoOverlap, but the explicit cut improves the relaxation.
        model.add(gaps[-1] >= 0)
        active_days.append(active)
    max_minutes = sum(r.duration_minutes for r in work.requests)
    loads = []
    for p in work.people:
        load = model.new_int_var(0, max_minutes, f"load:{p.id}")
        model.add(
            load
            == sum(
                r.duration_minutes * attendance[r.id, p.id]
                for r in work.requests
                if (r.id, p.id) in attendance
            )
        )
        loads.append(load)
    low = model.new_int_var(0, max_minutes, "low_load")
    high = model.new_int_var(0, max_minutes, "high_load")
    model.add_min_equality(low, loads)
    model.add_max_equality(high, loads)
    if work.max_load_difference_minutes is not None:
        model.add(high - low <= work.max_load_difference_minutes)
    for r in work.requests:
        meeting = warm_meetings.get(r.id)
        model.add_hint(present[r.id], int(meeting is not None))
        minute = (
            int((meeting.start - work.start).total_seconds() // 60) if meeting else 0
        )
        model.add_hint(starts[r.id], minute // work.grid_minutes)
        for p in work.people:
            if (r.id, p.id) in attendance:
                model.add_hint(
                    attendance[r.id, p.id],
                    int(meeting is not None and p.id in meeting.attendees),
                )
    model.add(
        sum(r.priority * present[r.id] for r in work.requests)
        >= warm_start.metrics.priority_scheduled
    )
    objectives = [
        ("priority", sum(r.priority * present[r.id] for r in work.requests), True),
        ("staffing", sum(unnecessary), False),
        ("fragmentation", sum(gaps), False),
        ("fairness", high - low, False),
        ("attendance", (len(active_days) + 1) * sum(optional) - sum(active_days), True),
    ]
    if previous is not None:
        changes = []
        by_id = {r.id: r for r in work.requests}
        for meeting in previous:
            if meeting.request_id not in by_id:
                continue
            r = by_id[meeting.request_id]
            minute = (meeting.start - work.start).total_seconds() / 60
            same = model.new_bool_var(f"unchanged:{r.id}")
            terms = [present[r.id]]
            if (
                minute % work.grid_minutes
                or minute < 0
                or minute > work.minutes - r.duration_minutes
                or (meeting.end - meeting.start).total_seconds()
                != r.duration_minutes * 60
                or any((r.id, pid) not in attendance for pid in meeting.attendees)
            ):
                model.add(same == 0)
            else:
                at_start = model.new_bool_var(f"same_start:{r.id}")
                model.add(
                    starts[r.id] == int(minute) // work.grid_minutes
                ).only_enforce_if(at_start)
                model.add(
                    starts[r.id] != int(minute) // work.grid_minutes
                ).only_enforce_if(at_start.Not())
                terms.append(at_start)
                for p in work.people:
                    if (r.id, p.id) in attendance:
                        a = attendance[r.id, p.id]
                        terms.append(a if p.id in meeting.attendees else a.Not())
                model.add_bool_and(terms).only_enforce_if(same)
                model.add_bool_or([term.Not() for term in terms]).only_enforce_if(
                    same.Not()
                )
            changes.append(1 - same)
        objectives.insert(1, ("stability", sum(changes), False))
    passes, best = [], None
    for name, objective, maximize in objectives:
        if maximize:
            model.maximize(objective)
        else:
            model.minimize(objective)
        engine = cp_model.CpSolver()
        engine.parameters.max_time_in_seconds = time_limit / len(objectives)
        # Work-based stopping is reproducible; wall time remains a safety ceiling.
        engine.parameters.max_deterministic_time = time_limit / (20 * len(objectives))
        engine.parameters.num_search_workers = 1
        engine.parameters.random_seed = 0
        status = engine.solve(model)
        success = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        passes.append(
            ObjectivePass(
                name=name,
                status=engine.status_name(status),
                value=round(engine.objective_value) if success else None,
                bound=engine.best_objective_bound if success else None,
            )
        )
        if not success:
            if status == cp_model.MODEL_INVALID:
                raise RuntimeError(f"invalid CP-SAT model: {model.validate()}")
            break
        best = engine
        value = round(engine.objective_value)
        model.add(objective == value)
        model.clear_hints()
        for var in all_bools + list(starts.values()):
            model.add_hint(var, engine.value(var))
    meetings = [] if best is not None else warm_start.meetings
    if best is not None:
        for r in work.requests:
            if best.value(present[r.id]):
                start = int(best.value(starts[r.id])) * work.grid_minutes
                meetings.append(
                    Meeting(
                        request_id=r.id,
                        start=work.instant(start),
                        end=work.instant(start + r.duration_minutes),
                        attendees=[
                            p.id
                            for p in work.people
                            if (r.id, p.id) in attendance
                            and best.value(attendance[r.id, p.id])
                        ],
                    )
                )
    algorithm = "cp-sat" if best is not None else "cp-sat/greedy-warm-start"
    result = result_for(work, meetings, perf_counter() - begun, algorithm)
    result.passes = passes
    if previous is not None:
        current = {m.request_id: m for m in result.meetings}
        ids = {r.id for r in work.requests}
        result.changed_requests = sorted(
            m.request_id
            for m in previous
            if m.request_id in ids
            and (
                m.request_id not in current
                or m.start != current[m.request_id].start
                or m.end != current[m.request_id].end
                or set(m.attendees) != set(current[m.request_id].attendees)
            )
        )
    return result


def validate_previous(work: Workload, previous: list[Meeting]):
    if len(previous) > 1200 or len({m.request_id for m in previous}) != len(previous):
        raise ValueError(
            "previous meeting IDs must be unique, with at most 1200 meetings"
        )
    ids = {p.id for p in work.people}
    for meeting in previous:
        if (
            not meeting.request_id
            or not meeting.attendees
            or len(set(meeting.attendees)) != len(meeting.attendees)
            or set(meeting.attendees) - ids
        ):
            raise ValueError(
                "previous meetings need unique known attendees and nonempty IDs"
            )
        Period(start=meeting.start, end=meeting.end)


def resolve(work: Workload, previous: list[Meeting], time_limit: float = 10.0):
    """Rebuild the edited workload, minimizing changes after scheduled priority."""
    return solve(work, time_limit, previous=previous)
