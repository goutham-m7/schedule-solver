"""Local, stateless FastAPI surface. Do not expose without auth and admission control."""

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import Field

from .explain import explain_result
from .greedy import greedy
from .models import StrictModel, Workload
from .render import calendar_html
from .solver import solve


class SolveInput(StrictModel):
    workload: Workload
    time_limit: float = Field(default=10, gt=0, le=120)
    explanations: bool = True


app = FastAPI(title="schedule-solver", version="0.1.0", description="Local explainable CP-SAT scheduling. Fixed-schedule insertion certificates, not global unsat claims.")


def run(input: SolveInput):
    try:
        result = solve(input.workload, input.time_limit)
        return explain_result(input.workload, result) if input.explanations else result
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/solve")
def solve_endpoint(input: SolveInput):
    return run(input)


@app.post("/compare")
def compare_endpoint(input: SolveInput):
    return {"optimized": run(input), "greedy": greedy(input.workload)}


@app.post("/calendar", response_class=HTMLResponse)
def calendar_endpoint(input: SolveInput):
    return calendar_html(input.workload, run(input))
