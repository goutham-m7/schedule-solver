"""Factual binding constraints and checked deletion-minimal insertion certificates.

Certificates hold the returned schedule fixed. They make no claim that moving
other meetings cannot accommodate the excluded request.
"""

from collections import Counter
from datetime import timedelta
from zoneinfo import ZoneInfo

from ortools.sat.python import cp_model

from .calendars import eligible, legal_starts, overlaps, padded, slots, static_reasons
from .models import Explanation, Request, Result, Workload


class InsertionModel:
    """Assumption literals permit both unsat cores and exact deletion checks."""

    def __init__(self, work: Workload, result: Result, request: Request):
        self.model = model = cp_model.CpModel()
        self.labels = {}
        self.request = request
        self.work = work
        self.start = start = model.new_int_var(
            0, max(0, len(slots(work, request)) - 1), "insertion_start"
        )
        self.people = {p.id: model.new_bool_var(f"insert:{p.id}") for p in work.people}
        model.add(sum(self.people.values()) >= 1)
        possible = list(slots(work, request))

        def label(name):
            if name not in self.labels:
                self.labels[name] = model.new_bool_var(name)
            return self.labels[name]

        for p in work.people:
            if not eligible(p, request):
                model.add(self.people[p.id] == 0).only_enforce_if(
                    label(f"eligibility:{request.id}")
                )
        if not possible:
            model.add(False).only_enforce_if(label(f"horizon:{request.id}"))
        else:
            allowed = [
                s
                for s in possible
                if work.instant(s * work.grid_minutes) >= request.earliest
                and work.instant(s * work.grid_minutes + request.duration_minutes)
                <= request.latest
            ]
            model.add_allowed_assignments(
                [start], [(s,) for s in allowed]
            ).only_enforce_if(label(f"window:{request.id}"))
        for pid in request.required_attendees:
            model.add(self.people[pid] == 1).only_enforce_if(label(f"required:{pid}"))
        for attr in ("skills", "roles"):
            for name, count in getattr(request, attr).items():
                model.add(
                    sum(
                        self.people[p.id]
                        for p in work.people
                        if name in getattr(p, attr)
                    )
                    >= count
                ).only_enforce_if(label(f"{attr}:{request.id}"))
        requests = {r.id: r for r in work.requests}
        loads = Counter()
        day_counts = Counter()
        for meeting in result.meetings:
            for pid in meeting.attendees:
                person = next(p for p in work.people if p.id == pid)
                day = (
                    meeting.start.astimezone(ZoneInfo(person.timezone))
                    .date()
                    .isoformat()
                )
                day_counts[pid, day] += 1
                loads[pid] += requests[meeting.request_id].duration_minutes
        for p in work.people:
            a = self.people[p.id]
            reasons = {s: static_reasons(work, request, p, s) for s in possible}
            for family in ("availability", "working_hours"):
                name = f"{family}:{p.id}"
                blocked = [s for s, why in reasons.items() if name in why]
                if blocked:
                    model.add_forbidden_assignments(
                        [start], [(s,) for s in blocked]
                    ).only_enforce_if([a, label(name)])
            for meeting in result.meetings:
                if p.id not in meeting.attendees:
                    continue
                before = meeting.start - timedelta(minutes=p.buffer_before_minutes)
                after = meeting.end + timedelta(minutes=p.buffer_after_minutes)
                blocked = [
                    s
                    for s in possible
                    if overlaps(*padded(work, request, p, s), before, after)
                ]
                if blocked:
                    model.add_forbidden_assignments(
                        [start], [(s,) for s in blocked]
                    ).only_enforce_if([a, label(f"meeting:{meeting.request_id}")])
            zone = ZoneInfo(p.timezone)
            days = {
                work.instant(s * work.grid_minutes).astimezone(zone).date().isoformat()
                for s in possible
            }
            for day in sorted(days):
                if day_counts[p.id, day] >= p.max_meetings_per_day:
                    blocked = [
                        s
                        for s in possible
                        if work.instant(s * work.grid_minutes)
                        .astimezone(zone)
                        .date()
                        .isoformat()
                        == day
                    ]
                    model.add_forbidden_assignments(
                        [start], [(s,) for s in blocked]
                    ).only_enforce_if([a, label(f"cap:{p.id}:{day}")])
        if work.max_load_difference_minutes is not None:
            for p in work.people:
                for q in work.people:
                    model.add(
                        loads[p.id]
                        + request.duration_minutes * self.people[p.id]
                        - loads[q.id]
                        - request.duration_minutes * self.people[q.id]
                        <= work.max_load_difference_minutes
                    ).only_enforce_if(label("fairness"))

    def check(self, enabled: set[str] | None = None, slot: int | None = None):
        if enabled is None:
            enabled = set(self.labels)
        self.model.clear_assumptions()
        self.model.add_assumptions(
            [var if name in enabled else var.Not() for name, var in self.labels.items()]
        )
        engine = cp_model.CpSolver()
        engine.parameters.max_time_in_seconds = 5
        engine.parameters.num_search_workers = 1
        if slot is not None:
            # Used only on a fresh model by the greedy baseline.
            self.model.add(self.start == slot)
        status = engine.solve(self.model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE, cp_model.INFEASIBLE):
            raise RuntimeError(
                f"insertion diagnosis did not finish: {engine.status_name(status)}"
            )
        return status != cp_model.INFEASIBLE, engine

    def minimal_conflict(self):
        feasible, engine = self.check()
        if feasible:
            return None
        by_index = {var.index: name for name, var in self.labels.items()}
        core = {
            by_index[i]
            for i in engine.sufficient_assumptions_for_infeasibility()
            if i in by_index
        }
        # A sufficient core is not necessarily minimal. Test each deletion.
        for name in sorted(core):
            if not self.check(core - {name})[0]:
                core.remove(name)
        return sorted(core)


def insertion_feasible(
    work: Workload, result: Result, request: Request, enabled: set[str] | None = None
) -> bool:
    return InsertionModel(work, result, request).check(enabled)[0]


def scheduled_facts(work, result, request, meeting):
    facts = [
        f"Priority {request.priority}; global lexicographic objectives select among feasible placements (not a unique-cause proof)."
    ]
    if meeting.start == request.earliest:
        facts.append("Binding earliest window boundary.")
    if meeting.end == request.latest:
        facts.append("Binding latest window boundary.")
    chosen_legal = None
    for p in work.people:
        if p.id not in meeting.attendees:
            continue
        legal = set(legal_starts(work, request, p))
        chosen_legal = legal if chosen_legal is None else chosen_legal & legal
        zone = ZoneInfo(p.timezone)
        local = meeting.start.astimezone(zone)
        same_day = [
            m
            for m in result.meetings
            if p.id in m.attendees and m.start.astimezone(zone).date() == local.date()
        ]
        if len(same_day) == p.max_meetings_per_day:
            facts.append(
                f"Binding cap: {p.id} has {len(same_day)} meetings on local {local.date()}."
            )
        before = meeting.start - timedelta(minutes=p.buffer_before_minutes)
        after = meeting.end + timedelta(minutes=p.buffer_after_minutes)
        if any(before == f.start or after == f.end for f in p.availability):
            facts.append(f"Binding free-time edge for {p.id}, including buffers.")
        if (
            before.astimezone(zone).time().replace(tzinfo=None) == p.working_hours.start
            or after.astimezone(zone).time().replace(tzinfo=None) == p.working_hours.end
        ):
            facts.append(f"Binding local working-hours edge for {p.id} ({p.timezone}).")
        for other in same_day:
            if other.request_id == request.id:
                continue
            other_before = other.start - timedelta(minutes=p.buffer_before_minutes)
            other_after = other.end + timedelta(minutes=p.buffer_after_minutes)
            if before == other_after or after == other_before:
                facts.append(
                    f"Binding neighbor/buffer edge for {p.id}: {other.request_id}."
                )
    facts.append(
        f"Chosen team has {len(chosen_legal or [])} static legal grid starts before other meetings and caps."
    )
    if request.skills or request.roles:
        facts.append(
            f"Team covers skills={request.skills}, roles={request.roles}; one person may cover multiple requirements."
        )
    return facts


def explain_result(work: Workload, result: Result) -> Result:
    meetings = {m.request_id: m for m in result.meetings}
    explanations = []
    for request in work.requests:
        if request.id in meetings:
            explanations.append(
                Explanation(
                    request_id=request.id,
                    kind="scheduled",
                    facts=scheduled_facts(work, result, request, meetings[request.id]),
                )
            )
        else:
            conflict = InsertionModel(work, result, request).minimal_conflict()
            explanations.append(
                Explanation(
                    request_id=request.id,
                    kind="insertable" if conflict is None else "insertion_conflict",
                    facts=[
                        "Insertion is feasible: omission reflects an objective trade-off or search time limit."
                        if conflict is None
                        else "Deletion-minimal conflict with the returned schedule held fixed; not minimum-cardinality and not a claim about rearranging meetings."
                    ],
                    conflict=conflict or [],
                    minimal=conflict is not None,
                )
            )
    return result.model_copy(update={"explanations": explanations})
