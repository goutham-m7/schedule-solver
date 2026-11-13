"""Seeded synthetic pods: contention, packing traps, and interchangeable staffing.

No customer/employer calendars, prompts, or names are used. Pods isolate scale
from density; this is a structured benchmark, not a claim about arbitrary graphs.
"""

from datetime import UTC, datetime, timedelta
from random import Random

from .models import Period, Person, Request, WorkingHours, Workload


def generate(people: int = 20, seed: int = 7) -> Workload:
    if people not in range(5, 101, 5):
        raise ValueError("people must be a multiple of 5 between 5 and 100")
    rng = Random(seed)
    origin = datetime(2027, 1, 4, 9, tzinfo=UTC)
    at = lambda minutes: origin + timedelta(minutes=minutes)
    persons, requests = [], []
    for pod in range(people // 5):
        ids = [f"p{pod * 5 + i:03d}" for i in range(5)]
        for i, pid in enumerate(ids):
            # Local hours agree with the same UTC window, exercising real TZ conversion.
            zone, hour = ("America/New_York", 4) if i == 4 else ("UTC", 9)
            persons.append(
                Person(
                    id=pid,
                    timezone=zone,
                    skills={f"build-{pod}"} if i >= 3 else {"planning"},
                    roles={"reviewer"} if i >= 3 else {"owner"},
                    availability=[
                        Period(
                            start=at(0 if i != 4 else 30),
                            end=at(180 if i != 3 else 150),
                        )
                    ],
                    working_hours=WorkingHours(
                        start=datetime(2027, 1, 4, hour).time(),
                        end=datetime(2027, 1, 4, hour + 3).time(),
                    ),
                    buffer_before_minutes=5 if i >= 3 else 0,
                    buffer_after_minutes=5 if i >= 3 else 0,
                    max_meetings_per_day=6,
                )
            )

        def add(name, duration, earliest, latest, required, priority=1, pod=pod, **kw):
            requests.append(
                Request(
                    id=f"pod{pod}-{name}",
                    duration_minutes=duration,
                    earliest=at(earliest),
                    latest=at(latest),
                    required_attendees=required,
                    priority=priority,
                    **kw,
                )
            )

        # Greedy commits a flexible low-value long meeting before two higher-total-value fixed ones.
        for i in range(2):
            add(f"long{i}", 120, 0, 120, [ids[i]], 3)
            add(f"first{i}", 60, 0, 60, [ids[i]], 2)
            add(f"second{i}", 60, 60, 120, [ids[i]], 2)
        # First-fit leaves a 90-minute internal gap; packing can eliminate it.
        add("anchor", 30, 120, 150, [ids[2]])
        add("flex", 30, 0, 120, [ids[2]])
        for i in range(4):
            add(
                f"build{i}",
                30,
                0,
                180,
                [],
                rng.randint(1, 4),
                skills={f"build-{pod}": 1},
                roles={"reviewer": 1},
            )
    return Workload(
        start=origin, end=at(180), people=persons, requests=requests, grid_minutes=15
    )
