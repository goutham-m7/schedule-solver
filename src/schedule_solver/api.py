"""Local, stateless FastAPI surface. Do not expose without auth and admission control."""

from importlib.metadata import version

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response
from pydantic import Field

from .calendars import export_ics
from .explain import explain_result
from .greedy import greedy
from .models import Meeting, Result, StrictModel, Workload
from .render import calendar_html
from .solver import resolve, solve


class SolveInput(StrictModel):
    workload: Workload
    time_limit: float = Field(default=10, gt=0, le=120)
    explanations: bool = True


class ResolveInput(SolveInput):
    previous: list[Meeting] = Field(max_length=1200)


app = FastAPI(
    title="schedule-solver",
    version=version("schedule-solver"),
    description="Local explainable CP-SAT scheduling. Fixed-schedule insertion certificates, not global unsat claims.",
)


def run(input: SolveInput):
    try:
        result = solve(input.workload, input.time_limit)
        return explain_result(input.workload, result) if input.explanations else result
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/solve", response_model=Result)
def solve_endpoint(input: SolveInput):
    return run(input)


@app.post("/compare", response_model=dict[str, Result])
def compare_endpoint(input: SolveInput):
    return {"optimized": run(input), "greedy": greedy(input.workload)}


@app.post("/calendar", response_class=HTMLResponse)
def calendar_endpoint(input: SolveInput):
    return calendar_html(input.workload, run(input))


@app.post("/resolve", response_model=Result)
def resolve_endpoint(input: ResolveInput):
    try:
        result = resolve(input.workload, input.previous, input.time_limit)
        return explain_result(input.workload, result) if input.explanations else result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post(
    "/export-ics",
    response_class=Response,
    responses={200: {"content": {"text/calendar": {}}}},
)
def export_endpoint(input: SolveInput):
    return Response(export_ics(input.workload, run(input)), media_type="text/calendar")
