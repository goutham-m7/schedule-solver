from schedule_solver.calendars import candidates_for
from schedule_solver.models import Workload


def test_redundant_requirement_prunes_only_unnecessary_role_specialists(payload):
    payload["people"].append({**payload["people"][0], "id": "bob", "skills": []})
    payload["requests"][0].update(
        required_attendees=[], skills={"python": 1}, roles={"reviewer": 1}
    )
    work = Workload.model_validate(payload)
    assert [p.id for p in candidates_for(work, work.requests[0])] == ["ada"]


def test_hard_fairness_disables_staffing_dominance(payload):
    payload["people"].append({**payload["people"][0], "id": "bob", "skills": []})
    payload["requests"][0].update(
        required_attendees=[], skills={"python": 1}, roles={"reviewer": 1}
    )
    payload["max_load_difference_minutes"] = 0
    work = Workload.model_validate(payload)
    assert len(candidates_for(work, work.requests[0])) == 2


def test_larger_role_cardinality_preserves_specialists(payload):
    payload["people"].append({**payload["people"][0], "id": "bob", "skills": []})
    payload["requests"][0].update(
        required_attendees=[], skills={"python": 1}, roles={"reviewer": 2}
    )
    work = Workload.model_validate(payload)
    assert len(candidates_for(work, work.requests[0])) == 2
