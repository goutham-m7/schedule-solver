"""Command-line composition: filesystem, environment, and optional network live here."""

import argparse
import json
import os
import sys
from pathlib import Path

import httpx
from pydantic import ValidationError

from .calendars import export_ics, import_ics
from .explain import explain_result
from .greedy import greedy
from .models import Workload
from .providers import MockNarrator, OpenAINarrator
from .render import calendar_html
from .solver import solve
from .synthetic import generate


def comparison_table(rows):
    lines = [
        "| People | Requests | Algorithm | Scheduled | Priority | Gap-min | Spread-min | Solve-s | Priority status |",
        "|---:|---:|:---|---:|---:|---:|---:|---:|:---|",
    ]
    for work, result in rows:
        m = result.metrics
        status = result.passes[0].status if result.passes else "n/a"
        lines.append(
            f"| {len(work.people)} | {len(work.requests)} | {result.algorithm} | {m.meetings_scheduled} | {m.priority_scheduled} | {m.gap_minutes} | {m.load_spread_minutes} | {m.solve_seconds:.3f} | {status} |"
        )
    return "\n".join(lines)


def parser():
    root = argparse.ArgumentParser(
        prog="schedule-solver",
        description="Explainable optimal scheduling, offline by default.",
    )
    commands = root.add_subparsers(dest="command", required=True)
    command = commands.add_parser("solve", help="Solve canonical JSON input")
    command.add_argument("input", type=Path)
    command.add_argument("--html", type=Path)
    command.add_argument(
        "--ics", type=Path, help="Export checked assignments as iCalendar"
    )
    command.add_argument("--time-limit", type=float, default=10)
    command.add_argument("--no-explanations", action="store_true")
    for name in ("demo", "benchmark"):
        command = commands.add_parser(name)
        if name == "demo":
            command.add_argument("--people", type=int, default=20)
            command.add_argument(
                "--provider", choices=["mock", "openai"], default="mock"
            )
            command.add_argument("--model", default="gpt-4o-mini")
        command.add_argument("--seed", type=int, default=7)
        command.add_argument("--time-limit", type=float, default=10)
        command.add_argument("--output", type=Path, default=Path("artifacts"))
    command = commands.add_parser(
        "import-ics",
        help="Merge explicit ICS busy blocks into a person's JSON calendar",
    )
    command.add_argument("input", type=Path)
    command.add_argument("person")
    command.add_argument("ics", type=Path)
    command.add_argument("--output", type=Path, required=True)
    command = commands.add_parser("serve")
    command.add_argument("--port", type=int, default=8000)
    return root


def main():
    args = parser().parse_args()
    try:
        if args.command == "serve":
            import uvicorn

            uvicorn.run("schedule_solver.api:app", host="127.0.0.1", port=args.port)
        elif args.command in ("solve", "import-ics"):
            work = Workload.model_validate_json(args.input.read_text())
            if args.command == "import-ics":
                person = next((p for p in work.people if p.id == args.person), None)
                if person is None:
                    raise ValueError(f"unknown person: {args.person}")
                person.busy.extend(
                    import_ics(args.ics.read_text(), person.timezone, work)
                )
                # Revalidate after merging so limits are not bypassed.
                work = Workload.model_validate(work.model_dump())
                args.output.write_text(work.model_dump_json(indent=2) + "\n")
                return
            result = solve(work, args.time_limit)
            if not args.no_explanations:
                result = explain_result(work, result)
            if args.html:
                args.html.write_text(calendar_html(work, result))
            if args.ics:
                args.ics.write_text(export_ics(work, result))
            print(result.model_dump_json(indent=2))
        else:
            sizes = [args.people] if args.command == "demo" else [20, 50, 100]
            rows, records = [], []
            args.output.mkdir(parents=True, exist_ok=True)
            for size in sizes:
                work = generate(size, args.seed)
                baseline, result = greedy(work), solve(work, args.time_limit)
                rows.extend([(work, baseline), (work, result)])
                records.append(
                    {
                        "people": size,
                        "seed": args.seed,
                        "workload": work.model_dump(mode="json"),
                        "greedy": baseline.model_dump(mode="json"),
                        "optimized": result.model_dump(mode="json"),
                    }
                )
            print(comparison_table(rows))
            if args.command == "demo":
                result = explain_result(work, result)
                args.output.joinpath("workload.json").write_text(
                    work.model_dump_json(indent=2) + "\n"
                )
                args.output.joinpath("result.json").write_text(
                    result.model_dump_json(indent=2) + "\n"
                )
                args.output.joinpath("calendar.html").write_text(
                    calendar_html(work, result)
                )
                args.output.joinpath("schedule.ics").write_text(
                    export_ics(work, result)
                )
                print("\nExplanations (fixed-schedule insertion certificates):")
                with httpx.Client() as client:
                    narrator = (
                        MockNarrator()
                        if args.provider == "mock"
                        else OpenAINarrator(
                            os.environ.get(
                                "SCHEDULE_LLM_BASE_URL", "https://api.openai.com/v1"
                            ),
                            os.environ.get("SCHEDULE_LLM_API_KEY", ""),
                            args.model,
                            client,
                        )
                    )
                    for explanation in result.explanations[:12]:
                        print(narrator.describe(explanation))
                print(f"\nCalendar: {args.output / 'calendar.html'}")
            else:
                args.output.joinpath("benchmark.json").write_text(
                    json.dumps(records, indent=2) + "\n"
                )
                args.output.joinpath("benchmark.md").write_text(
                    comparison_table(rows) + "\n"
                )
    except (
        OSError,
        ValueError,
        ValidationError,
        RuntimeError,
        httpx.HTTPError,
        KeyError,
        IndexError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)
