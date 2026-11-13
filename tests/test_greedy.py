from schedule_solver.greedy import greedy
from schedule_solver.models import Workload
from schedule_solver.solver import solve
from test_solver import request


def test_greedy_is_input_order_not_priority_order(payload):
    payload["requests"] = [request("first"), request("important", priority=10)]
    work = Workload.model_validate(payload)
    assert greedy(work).meetings[0].request_id == "first"
    assert solve(work).metrics.priority_scheduled == 10


def test_greedy_flexible_request_blocks_two_fixed_requests(payload):
    payload["requests"] = [request("flex", end=11, duration=120), request("a"), request("b", start=10, end=11)]
    work = Workload.model_validate(payload)
    assert greedy(work).metrics.meetings_scheduled == 1
    assert solve(work).metrics.meetings_scheduled == 2


def test_greedy_skills_and_caps(payload):
    payload["people"][0]["max_meetings_per_day"] = 1
    payload["requests"] = [request(str(i), required_attendees=[], skills={"python": 1}) for i in range(3)]
    assert greedy(Workload.model_validate(payload)).metrics.meetings_scheduled == 1
