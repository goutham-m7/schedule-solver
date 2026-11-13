"""Optional-interval CP-SAT model with explicit lexicographic optimization."""

from collections import defaultdict
from time import perf_counter
from zoneinfo import ZoneInfo

from ortools.sat.python import cp_model

from .calendars import legal_starts, slots
from .metrics import result_for
from .models import Meeting, ObjectivePass, Workload


def eligible(person, request):
    return (
        person.id in request.required_attendees + request.optional_attendees
        or bool(person.skills & request.skills.keys())
        or bool(person.roles & request.roles.keys())
    )


def solve(work: Workload, time_limit: float = 10.0):
    """Bound each optimization pass by a fifth of time_limit; return honest statuses.

    Model construction and explanations are not included in CP search's time limit.
    A timed-out pass with no incumbent preserves the preceding pass's solution.
    """
    if not 0 < time_limit <= 120:
        raise ValueError("time_limit must be in (0, 120] seconds")
    begun = perf_counter()
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
        for p in work.people:
            if not eligible(p, r):
                continue
            legal = legal_starts(work, r, p)
            if not legal:
                continue
            a = attendance[r.id, p.id] = model.new_bool_var(f"attend:{r.id}:{p.id}")
            all_bools.append(a)
            candidates[p.id] = a
            model.add(a <= y)
            model.add_allowed_assignments(
                [start], [(s,) for s in legal]
            ).only_enforce_if(a)
            interval = model.new_optional_fixed_size_interval_var(
                start * work.grid_minutes - p.buffer_before_minutes,
                r.duration_minutes + p.buffer_before_minutes + p.buffer_after_minutes,
                a,
                f"interval:{r.id}:{p.id}",
            )
            intervals[p.id].append(interval)
            zone = ZoneInfo(p.timezone)
            days = sorted(
                {
                    work.instant(s * work.grid_minutes)
                    .astimezone(zone)
                    .date()
                    .isoformat()
                    for s in legal
                }
            )
            for day in days:
                on_day = model.new_bool_var(f"day:{r.id}:{p.id}:{day}")
                model.add(on_day <= a)
                model.add_allowed_assignments(
                    [start, on_day],
                    [
                        (
                            s,
                            int(
                                work.instant(s * work.grid_minutes)
                                .astimezone(zone)
                                .date()
                                .isoformat()
                                == day
                            ),
                        )
                        for s in legal
                    ],
                ).only_enforce_if(a)
                daily[p.id, day].append((r, start, on_day))
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
    objectives = [
        ("priority", sum(r.priority * present[r.id] for r in work.requests), True),
        ("staffing", sum(unnecessary), False),
        ("fragmentation", sum(gaps), False),
        ("fairness", high - low, False),
        ("attendance", (len(active_days) + 1) * sum(optional) - sum(active_days), True),
    ]
    passes, best = [], None
    for name, objective, maximize in objectives:
        if maximize:
            model.maximize(objective)
        else:
            model.minimize(objective)
        engine = cp_model.CpSolver()
        engine.parameters.max_time_in_seconds = time_limit / len(objectives)
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
    meetings = []
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
    result = result_for(work, meetings, perf_counter() - begun, "cp-sat")
    result.passes = passes
    return result
