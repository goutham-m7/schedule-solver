# Explainable optimal scheduling

## Problem and scope
Assign bounded, discrete meeting requests to people and UTC start instants while
respecting each person's local calendar. This project uses only synthetic data.
Python 3.12, OR-Tools CP-SAT and FastAPI keep optimization and HTTP contracts in one
small, typed package. No database, network calendar writes, or LLM is needed.

## Contract
Input is strict JSON: timezone-aware timestamps; IANA person time zones; explicit
availability intervals (positive/free time), local weekday working hours, busy
intervals, skills, roles, daily meeting caps and before/after buffers. Request
windows bound the entire meeting, not its start alone. All intervals are half-open.
Starts lie on a UTC grid anchored at the workload horizon. Durations and buffers
are integral minutes, not rounded. Buffers must fit free/working time and not
intersect busy time; the gap between adjacent meetings includes both buffers.
Each selected person may cover multiple required skills/roles. Optional attendees
are best-effort, never mandatory; extra eligible skill providers are not rewarded.

## CP-SAT design
One scheduled Boolean and one grid start integer per request; one attendance
Boolean and optional interval per eligible person/request. Required attendance is
equivalent to scheduling. Skill and role cardinalities are conditional on presence.
Allowed start tables enforce free/busy, working hours and request windows.
NoOverlap operates on padded intervals. Reified local-date membership enforces
caps. Optional hard workload-wide load-spread limit applies to all people.

Lexicographic passes maximize priority, minimize daily fragmentation (gap minutes
plus one grid unit per active person-day), minimize total minute-load spread, then
maximize optional attendance and minimize unnecessary staffing. A pass fixes its
incumbent objective before the next pass. If time expires, preserve the last feasible
incumbent and report each pass's status/bound: never claim global optimality unless
all passes prove OPTIMAL. No assumption that a five-second solution is optimal.
Greedy uses the same legal starts and staffing constraints, but input-order first-fit.

## Explainability
Scheduled: report feasible start count, tight window/free/working boundaries, caps,
neighbor buffers, staffing requirements and global objective contributions. These
are factual local constraints, not an invented causal proof of a unique optimum.

Unscheduled: compute a deletion-minimal conflict certificate relative to the
**returned schedule held fixed**. A small CP-SAT insertion model selects a start and
team for the excluded request. Its named constraints are request window, each
person's availability/working hours, skills/roles, each retained meeting's padded
occupancy, daily caps and optional hard fairness. Delete constraints one by one;
retain one only if removing it admits insertion. Every returned member is necessary
(inclusion-minimal, not minimum cardinality). The universe includes all grid starts
inside the horizon and all people. If insertion is possible, say so (objective
trade-off or time limit), not infeasible. Diagnostic timeouts are explicit errors,
not false certificates. This does not prove that rearrangement cannot admit it.

## Calendars and presentation
JSON is canonical. ICS import accepts explicit VEVENT busy periods, TZID and
all-day dates, merges them into a person's busy list. Reject recurrence rules,
recurrence dates, exclusions and floating timestamps rather than silently missing
instances. Transparent/cancelled events do not block. No remote calendar fetches.
FastAPI: POST /solve, POST /compare, POST /calendar, GET /health.
CLI: solve, demo, benchmark, import-ics, serve. Static HTML escapes all user data,
shows UTC and each attendee's local time, and uses no external assets.

## Optional language layer
Deterministic mock narrator runs offline. OpenAI-compatible provider receives only
an already-computed certificate and returns commentary; it never changes solver
facts or certificates. Key and base URL are injected from environment at CLI
composition. HTTP errors remain errors; never fabricate a fallback response.

## Alternatives and trade-offs
Enumerated team/slot combinations explode with 100 people: shared starts and
attendance Booleans avoid team enumeration in CP-SAT. Continuous starts would
remove grid loss but complicate transparent finite insertion certificates. Weighted
single objectives can sacrifice priority; lexicographic passes do not. Minimal
unsat subsets with all meetings movable are expensive and semantically different;
fixed-schedule certificates answer the actionable insertion question explicitly.
No persistence/auth/multi-tenant service: bind localhost; do not expose to untrusted
traffic. Bound input sizes, solve duration, and diagnose duration.

## Verification and acceptance
Real CP-SAT tests cover priority optimality against exhaustive small cases, legal
intervals, combined buffers, time zones/DST, daily caps, skills/roles/optionals,
fragmentation and fairness. Certificate tests remove every member and verify
feasibility; impossible static requests and objective/time-limit omissions differ.
Real HTTP TestClient and subprocess CLI tests prove the public interfaces. ICS tests
exercise actual parser input including rejection. MockTransport alone replaces the
paid LLM HTTP boundary. Benchmarks use seeded synthetic 20/50/100-person workloads,
compare both schedulers under the same constraints, and record wall-clock time,
weighted priority, meetings and gap minutes. Demo captures real output and HTML.
Not tested: hosted deployment, provider credentials or remote calendar integration
(out of scope); third-party CP-SAT implementation (tested via behavioral oracles).
