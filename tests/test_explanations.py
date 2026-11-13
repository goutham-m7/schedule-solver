from test_solver import request

from schedule_solver.explain import explain_result, insertion_feasible
from schedule_solver.models import Workload
from schedule_solver.solver import solve


def test_conflict_is_irreducible_against_fixed_schedule(payload):
    payload["requests"] = [request("chosen", priority=5), request("excluded")]
    work = Workload.model_validate(payload)
    result = explain_result(work, solve(work))
    explanation = next(e for e in result.explanations if e.request_id == "excluded")
    assert explanation.kind == "insertion_conflict"
    assert explanation.minimal
    assert "meeting:chosen" in explanation.conflict
    assert not insertion_feasible(
        work, result, work.requests[1], set(explanation.conflict)
    )
    for member in explanation.conflict:
        assert insertion_feasible(
            work, result, work.requests[1], set(explanation.conflict) - {member}
        )


def test_missing_skill_certificate(payload):
    payload["requests"] = [
        request("unknown", required_attendees=[], skills={"quantum": 1})
    ]
    work = Workload.model_validate(payload)
    result = explain_result(work, solve(work))
    e = result.explanations[0]
    # Several inclusion-minimal cores can exist; no eligible person is also
    # sufficient when the requested skill is absent from the entire roster.
    assert e.conflict in (["skills:unknown"], ["eligibility:unknown"])
    assert e.minimal
    assert not insertion_feasible(work, result, work.requests[0], set(e.conflict))
    assert insertion_feasible(work, result, work.requests[0], set())


def test_cap_certificate(payload):
    payload["people"][0]["max_meetings_per_day"] = 0
    work = Workload.model_validate(payload)
    e = explain_result(work, solve(work)).explanations[0]
    assert any(label.startswith("cap:ada:") for label in e.conflict)


def test_scheduled_explanation_reports_tight_window(payload):
    payload["requests"] = [request("fixed")]
    work = Workload.model_validate(payload)
    e = explain_result(work, solve(work)).explanations[0]
    assert e.kind == "scheduled"
    assert any("earliest" in fact for fact in e.facts)


def test_insertable_omission_not_claimed_infeasible(payload):
    work = Workload.model_validate(payload)
    result = solve(work)
    result.meetings = []
    result.unscheduled = ["review"]
    e = explain_result(work, result).explanations[0]
    assert e.kind == "insertable"
    assert not e.minimal
