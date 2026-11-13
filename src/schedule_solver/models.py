"""Strict, timezone-aware public input and result contracts."""

from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Period(StrictModel):
    start: AwareDatetime
    end: AwareDatetime

    @model_validator(mode="after")
    def ordered(self):
        if self.start >= self.end:
            raise ValueError("period end must follow start")
        if any(t.second or t.microsecond for t in (self.start, self.end)):
            raise ValueError("timestamps must have minute precision")
        return self


class WorkingHours(StrictModel):
    weekdays: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])
    start: time = time(9)
    end: time = time(17)

    @model_validator(mode="after")
    def ordered(self):
        if self.start >= self.end or any(d not in range(7) for d in self.weekdays):
            raise ValueError(
                "working hours need same-day start < end and weekdays 0..6"
            )
        if any(t.tzinfo or t.second or t.microsecond for t in (self.start, self.end)):
            raise ValueError("working hours must be naive local minute-precision times")
        return self


class Person(StrictModel):
    id: str = Field(min_length=1, max_length=100)
    timezone: str
    skills: set[str] = Field(default_factory=set)
    roles: set[str] = Field(default_factory=set)
    availability: list[Period] = Field(min_length=1, max_length=500)
    busy: list[Period] = Field(default_factory=list, max_length=1000)
    working_hours: WorkingHours = Field(default_factory=WorkingHours)
    max_meetings_per_day: int = Field(default=8, ge=0, le=100)
    buffer_before_minutes: int = Field(default=0, ge=0, le=240)
    buffer_after_minutes: int = Field(default=0, ge=0, le=240)

    @field_validator("timezone")
    @classmethod
    def known_zone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("unknown IANA time zone") from exc
        return value


class Request(StrictModel):
    id: str = Field(min_length=1, max_length=100)
    duration_minutes: int = Field(ge=1, le=1440)
    earliest: AwareDatetime
    latest: AwareDatetime
    required_attendees: list[str] = Field(default_factory=list)
    optional_attendees: list[str] = Field(default_factory=list)
    skills: dict[str, int] = Field(default_factory=dict)
    roles: dict[str, int] = Field(default_factory=dict)
    priority: int = Field(default=1, ge=1, le=1000)

    @model_validator(mode="after")
    def valid(self):
        Period(start=self.earliest, end=self.latest)
        if not (self.required_attendees or self.skills or self.roles):
            raise ValueError(
                "a request needs required attendees or skill/role requirements"
            )
        for group in (self.required_attendees, self.optional_attendees):
            if len(group) != len(set(group)):
                raise ValueError("attendee lists must be unique")
        if set(self.required_attendees) & set(self.optional_attendees):
            raise ValueError("required and optional attendees must be disjoint")
        if any(
            not k or type(n) is not int or n < 1 or n > 100
            for d in (self.skills, self.roles)
            for k, n in d.items()
        ):
            raise ValueError("skill/role cardinalities must be integers 1..100")
        return self


class Workload(Period):
    people: list[Person] = Field(min_length=1, max_length=100)
    requests: list[Request] = Field(max_length=500)
    grid_minutes: int = Field(default=15, ge=1, le=60)
    max_load_difference_minutes: int | None = Field(default=None, ge=0, le=100000)

    @model_validator(mode="after")
    def references(self):
        ids = [p.id for p in self.people]
        if len(ids) != len(set(ids)) or len({r.id for r in self.requests}) != len(
            self.requests
        ):
            raise ValueError("person and request IDs must be unique")
        if any(
            set(r.required_attendees + r.optional_attendees) - set(ids)
            for r in self.requests
        ):
            raise ValueError("request references an unknown person")
        if (self.end - self.start).total_seconds() > 7 * 86400:
            raise ValueError("horizon must not exceed seven days")
        return self

    @property
    def minutes(self):
        return int(
            (self.end.astimezone(UTC) - self.start.astimezone(UTC)).total_seconds()
            // 60
        )

    def instant(self, minute: int) -> datetime:
        from datetime import timedelta

        return self.start.astimezone(UTC) + timedelta(minutes=minute)


class Meeting(StrictModel):
    request_id: str
    start: AwareDatetime
    end: AwareDatetime
    attendees: list[str]


class ObjectivePass(StrictModel):
    name: str
    status: str
    value: int | None
    bound: float | None


class Metrics(StrictModel):
    meetings_scheduled: int
    priority_scheduled: int
    gap_minutes: int
    active_person_days: int
    load_spread_minutes: int
    solve_seconds: float


class Explanation(StrictModel):
    request_id: str
    kind: str
    facts: list[str]
    conflict: list[str] = Field(default_factory=list)
    minimal: bool = False


class Result(StrictModel):
    algorithm: str
    meetings: list[Meeting]
    unscheduled: list[str]
    metrics: Metrics
    passes: list[ObjectivePass] = Field(default_factory=list)
    explanations: list[Explanation] = Field(default_factory=list)
