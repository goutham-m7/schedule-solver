# schedule-solver

Offline CP-SAT meeting scheduling with calendar constraints and checked conflict explanations.

## The problem

Meeting organizers need to know which constraints prevent a request from fitting,
not just see an empty booking page: free calendar time alone does not establish
bookability.

- [Google Calendar's availability documentation](https://support.google.com/calendar/answer/11423292?hl=en)
  warns that its default **4-hour minimum notice** can hide all same-day availability,
  and documents buffers and daily booking caps (undated; accessed 2026-11-14).
- [Calendly's troubleshooting guide](https://calendly.com/help/how-to-troubleshoot-unavailable-times-that-should-be-available)
  lists distinct blockers including duration, buffers, host availability and unfair
  distribution; organizers must open its diagnostic tool to inspect the reasons
  (updated 2026-10-26).

These products do provide diagnostics; the problem is understanding interacting
constraints, not a claim that no scheduler explains failures.

schedule-solver schedules an offline workload and checks conflict certificates for
excluded requests against the fixed resulting schedule; those certificates do not
prove that rearranging every meeting could never fit the request.

**v0.2.0:** recurring busy calendars, stable re-solving, small minimum-cardinality
conflicts, checked ICS export, and benchmark curves through 500 people.

On a **synthetic 200-person workload**, the solver scheduled **400 meetings versus
first-fit's 320**, with the priority objective proven optimal, in **7.000 seconds**.
At 500 people the same budget produced only 804 versus 800: this is not a claim that
large instances are solved optimally. Full curves and limitations are below.

## Quickstart

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12 or newer.

```sh
uv sync --frozen
uv run schedule-solver demo --people 5 --seed 7 --time-limit 10 --output artifacts/demo
# Open artifacts/demo/calendar.html or import artifacts/demo/schedule.ics.
```

Measured local output; timing varies:

```text
| People | Requests | Algorithm | Scheduled | Priority | Gap-min | Spread-min | Solve-s | Priority status |
|---:|---:|:---|---:|---:|---:|---:|---:|:---|
| 5 | 12 | greedy-first-fit | 8 | 18 | 120 | 60 | 0.001 | n/a |
| 5 | 12 | cp-sat | 10 | 20 | 30 | 60 | 0.063 | OPTIMAL |
```

The demo writes `workload.json`, `result.json`, `calendar.html` and `schedule.ics`.
Scheduling, explanations and export need no keys or network after installation.
The optional narrator is separate from the mathematical decisions.

[Changelog](CHANGELOG.md) · [Completed milestone and delivery commits](ROADMAP.md) ·
[Design](DESIGN.md) · [v0.2 technical decisions](docs/v0.2-design.md)

## Workload and constraints

See [examples/workload.json](examples/workload.json). IDs are strings; timestamps
need explicit offsets and minute precision. Availability means **free time**;
`busy` and imported ICS events subtract from it. IANA time zones define local
working hours and daily caps. Weekdays run Monday=0 through Sunday=6.

Requests specify `duration_minutes`, `priority`, `earliest`, `latest`, required and
optional attendees, and minimum skill/role counts. One person can cover multiple
requirements. `latest` bounds the meeting's **end**. Combined per-person buffers
are hard constraints. Optional `max_load_difference_minutes` is a hard horizon-wide
meeting-minute spread limit, not capacity-normalized utilization.

Limits: 500 people, 1200 requests, seven days. These are input limits, not latency
or optimality guarantees. Meetings and padded working hours stay within one
attendee-local day; overnight working-hour definitions are rejected.

```sh
uv run schedule-solver solve examples/workload.json --html artifacts/custom.html --ics artifacts/custom.ics
uv run schedule-solver import-ics examples/workload.json p000 examples/busy.ics --output artifacts/merged.json
uv run schedule-solver solve artifacts/merged.json
```

CLI errors exit with status 2 and a short message. IDs and calendar output are
escaped by the rendering/serialization libraries, not interpolated as markup.

## Recurring busy calendars

`import-ics` supplies the workload horizon automatically. Python callers supply a
`Period` when importing RRULE, RDATE or EXDATE:

```python
from schedule_solver.calendars import import_ics
from schedule_solver.models import Period

horizon = Period(start="2027-03-07T00:00:00Z", end="2027-03-23T00:00:00Z")
text = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:weekly-review
DTSTART;TZID=America/New_York:20270307T090000
DTEND;TZID=America/New_York:20270307T100000
RRULE:FREQ=WEEKLY;COUNT=3
EXDATE;TZID=America/New_York:20270321T090000
END:VEVENT
END:VCALENDAR
"""
periods = import_ics(text, "America/New_York", horizon)
```

Local recurrence times survive DST: the test above yields starts at 14:00 UTC
before the spring transition and 13:00 UTC afterward. EXDATE removes instances;
RDATE adds instances. All-day dates use local midnights. Nonexistent local instances
are skipped without consuming COUNT; ambiguous times use the first fold. DTEND
preserves elapsed duration; DURATION adds local days before elapsed hours/minutes.
Returned intervals are clipped to the supplied horizon and merged.

Floating times, detached `RECURRENCE-ID` overrides, EXRULE and malformed properties
fail closed. Cancelled/transparent events do not block. Expansion has a per-event
10,000-instance traversal limit, including historical instances; long historical
or high-frequency series can hit it even for a short requested horizon. No remote
calendar fetch or provider synchronization is implemented.

## Re-solve after an edit

```python
from schedule_solver.solver import resolve, solve
from schedule_solver.synthetic import generate

work = generate(5, seed=7)
before = solve(work)
edited = work.model_copy(deep=True)
edited.requests = [r for r in edited.requests if r.id != "pod0-flex"]
after = resolve(edited, before.meetings)
print(after.changed_requests)
```

Pass the **complete edited workload** plus previous assignments. Add a request to
add a meeting, edit its window/duration/team requirements to move it, or remove its
ID to cancel it. Missing IDs are explicit cancellations and do not count as
unintended changes. Structural errors in previous assignments are rejected, but
old assignments may violate newly edited calendars.

Priority remains first. The next pass minimizes the number of retained requests
whose start, end, attendee set or scheduled presence changes. Ordinary packing,
staffing and fairness tie-breakers follow. This counts changed meetings, not moved
minutes. `changed_requests` reports the affected retained IDs. Cancelled IDs cannot
be distinguished from typos without the old workload: preserve IDs carefully.

This is a stateless model rebuild, not an in-memory incremental CP-SAT session.
A `FEASIBLE` stability pass gives an incumbent, not a minimal-change proof;
`OPTIMAL` proves stability only conditional on the earlier fixed priority value.
Very small budgets can return the greedy fallback without reaching stability.

## Explanations and export

Scheduled explanations report factual tight windows, working-hour/free-time edges,
neighbor buffers, caps and staffing. They are not unique-cause proofs.

Excluded requests get **fixed-schedule insertion** certificates:

- At most 12 constraint labels: enumerate the entire label universe in increasing
  subset size and prove `guarantee="minimum-cardinality"`.
- Larger universes: reduce an assumption core by deletion, returning
  `guarantee="inclusion-minimal"`. Removing any member admits insertion relative
  to the remaining named constraints, with other labels relaxed.
- Feasible insertion: return `insertable`, not a fabricated conflict.
- Diagnostic timeout: fail instead of claiming an unchecked proof.

Existing assignments remain frozen in every certificate. Neither guarantee proves
that rearranging other meetings cannot fit the target. Small exhaustive searches
have a five-second deadline in addition to bounded individual feasibility checks.

`export_ics(workload, result)` independently checks IDs, duration/grid, staffing,
free/busy calendars, buffered overlap, daily caps and hard fairness. Exported UTC
VEVENTs use deterministic request-derived UIDs and escaped request IDs as summaries.
Attendee IDs are JSON in `X-SCHEDULE-ATTENDEES`, not fabricated email addresses.
Use globally unique request IDs when combining unrelated workloads in one calendar:
reusing an ID reuses its UID. No invites are sent. Round-trip parsing is tested;
Google/Outlook UI import has not been tested.

## Local HTTP API

```sh
uv run schedule-solver serve --port 8000
# Interactive docs: http://127.0.0.1:8000/docs
# OpenAPI schema:   http://127.0.0.1:8000/openapi.json
```

| Endpoint | Request / result |
|---|---|
| `GET /health` | Liveness, no provider dependency |
| `POST /solve` | Solve input → typed Result |
| `POST /compare` | Solve input → optimized and greedy Results |
| `POST /calendar` | Solve input → script-free HTML |
| `POST /export-ics` | Solve input → `text/calendar` |
| `POST /resolve` | Solve input plus `previous: Meeting[]` → typed Result |

Solve input is `{"workload": ..., "time_limit": 10, "explanations": true}`.
Set `explanations` false when certificates are unnecessary. Invalid input returns
422; unfinished diagnosis returns 503. OpenAPI includes request and Result schemas.
The service binds loopback and has **no authentication, persistence or production
admission control**. Do not expose it publicly as-is.

## Optimization and benchmarks

The solver uses shared integer starts, optional buffered attendee intervals,
`NoOverlap`, local-date caps and domain-filtered calendar feasibility. Ordinary
lexicographic passes maximize priority, minimize unnecessary staffing, minimize
person-day gaps, minimize load spread, then maximize optional attendance and reduce
active person-days. Re-solving inserts stability immediately after priority.
Each pass fixes its actual returned integer expression value; a regression covers
a time-limited OR-Tools objective summary that differed from its assignment.

`--time-limit T` bounds each of N passes by T/N wall seconds and T/(20N)
deterministic solver-work units. Construction, greedy warm start, explanations,
serialization and process startup are **outside the search ceiling**. Reported
solve time includes construction and the warm start, but not explanations or I/O.
One worker, fixed solver seed and seeded synthetic workloads make comparisons
repeatable unless the wall ceiling fires. More budget does not promise monotonic
quality on arbitrary workloads; secondary optima are conditional on earlier values.

```sh
uv run schedule-solver benchmark --sizes 200 500 --families independent ring --budgets 0.1 10 60 --seed 7 --output artifacts/v02-final-curves
```

Measured on macOS 27.2 arm64, Python 3.12.15, OR-Tools 9.15.6755, uv 0.13.5.
All inputs are **synthetic**. Independent pods repeat contention/packing motifs;
the ring family shares specialist skills across neighboring pods. Neither is an
arbitrary dense scheduling graph. Both algorithms receive identical workloads.

| Family | People | Search budget | Greedy meetings | Solver meetings | Priority / upper bound | Priority status | Solve seconds |
|---|---:|---:|---:|---:|---:|---|---:|
| Independent | 200 | 0.1 | 320 | 320 | 714 / — | UNKNOWN, greedy fallback | 0.762 |
| Independent | 200 | 10 | 320 | 399 | 792 / 794 | FEASIBLE | 1.517 |
| Independent | 200 | 60 | 320 | 400 | 794 / 794 | OPTIMAL | 7.000 |
| Independent | 500 | 0.1 | 800 | 800 | 1780 / — | UNKNOWN, greedy fallback | 5.429 |
| Independent | 500 | 10 | 800 | 800 | 1780 / — | UNKNOWN, greedy fallback | 6.317 |
| Independent | 500 | 60 | 800 | 804 | 1784 / 1980 | FEASIBLE | 9.446 |
| Ring | 200 | 0.1 | 320 | 320 | 714 / — | UNKNOWN, greedy fallback | 0.774 |
| Ring | 200 | 10 | 320 | 367 | 719 / 794 | FEASIBLE | 1.669 |
| Ring | 200 | 60 | 320 | 400 | 794 / 794 | OPTIMAL | 15.176 |
| Ring | 500 | 0.1 | 800 | 800 | 1780 / — | UNKNOWN, greedy fallback | 5.528 |
| Ring | 500 | 10 | 800 | 800 | 1780 / — | UNKNOWN, greedy fallback | 6.325 |
| Ring | 500 | 60 | 800 | 805 | 1783 / 1980 | FEASIBLE | 10.762 |

At 200 people / budget 60, independent gaps increased from greedy's 4800 to 4980
minutes and spread increased from 60 to 90. Higher priority is not a win on every
secondary metric. At 500 people the short budgets found no CP incumbent; fallback
results are labelled, not reported as optimal. The 0.1 budget still takes seconds
because construction and greedy dominate. These results identify a scalability
limit rather than conceal it.

[Full tables](evidence/v0.2-curves.md) · [Metrics, bounds and environment](evidence/v0.2-curves.json).
All 24 resulting greedy/optimized schedules passed independent hard-constraint
validation. The benchmark writes full workload/result JSON and environment metadata
so individual runs can be inspected or regenerated.

## Tests and distribution builds

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest --cov=schedule_solver --cov-report=term-missing --cov-fail-under=90 -q
uv build
```

Observed: **129 tests passed, 95.91% statement coverage**. Tests execute real
OR-Tools, dateutil, icalendar, CLI subprocesses and FastAPI contracts, including DST
gaps/folds, recurrence exclusions, re-solve stability, exhaustive small conflict
subsets, malformed assignments and the native objective-handoff regression.
The upstream Starlette/httpx deprecation warning remains visible.

Wheel and sdist build locally as `dist/schedule_solver-0.2.0-py3-none-any.whl` and
`dist/schedule_solver-0.2.0.tar.gz`. Nothing is published or tagged.
[Fresh local clone and isolated wheel evidence](evidence/v0.2-verification.md)
records installation, full tests, lint, formatting, build and the offline demo.
CI uses the same lint, format, coverage and demo commands; no live LLM key is used.

## Optional narrator and remaining limits

Default `--provider mock` is deterministic and offline. Explicit OpenAI-compatible
narration uses `SCHEDULE_LLM_BASE_URL`, `SCHEDULE_LLM_API_KEY`, and `--provider openai
--model ...`. Only computed explanations are sent, but those can contain attendee
IDs and times: obtain permission before sending private calendar data. A narrator
cannot alter assignments or proof certificates. Real hosted-provider behavior has
not been tested with a paid key; HTTP boundaries use an injected test transport.

The UTC grid can miss a continuous-time start. Fairness is not capacity-normalized.
Rooms/resources, weighted preferred times/back-to-back penalties, detached calendar
overrides, globally movable repair proofs and worker-isolated production HTTP jobs
are future work, not stubbed modules. See [ROADMAP.md](ROADMAP.md).

MIT licensed. Original code and synthetic inputs; no employer code, prompts or data.
