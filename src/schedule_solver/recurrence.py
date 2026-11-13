"""Bounded RFC 5545 recurrence sets; detached overrides deliberately fail closed."""

from datetime import UTC, date, datetime, time, timedelta

from dateutil.rrule import rrulestr
from dateutil.tz import datetime_exists

from .models import Period


def event_periods(event, zone, horizon, max_occurrences):
    if any(key in event for key in ("RECURRENCE-ID", "EXRULE")):
        raise ValueError("unsupported recurrence override or EXRULE")
    recurring = any(key in event for key in ("RRULE", "RDATE", "EXDATE"))
    if recurring and horizon is None:
        raise ValueError("recurrence requires an explicit horizon")
    if "DTSTART" not in event:
        raise ValueError("VEVENT requires DTSTART")
    start = event.decoded("DTSTART")
    if "DTEND" in event and "DURATION" in event:
        raise ValueError("VEVENT cannot specify both DTEND and DURATION")
    if "DTEND" in event:
        end = event.decoded("DTEND")
    elif "DURATION" in event:
        end = start + event.decoded("DURATION")
    elif type(start) is date:
        end = start + timedelta(days=1)
    else:
        raise ValueError("timed VEVENT requires DTEND or DURATION")
    all_day = type(start) is date
    if isinstance(start, datetime) != isinstance(end, datetime):
        raise ValueError("DTSTART and DTEND must have the same value type")

    def local(value):
        if isinstance(value, datetime):
            if value.tzinfo is None:
                raise ValueError("floating ICS timestamps are not supported")
            return value
        return datetime.combine(value, time(), zone)

    first, last = local(start), local(end)
    Period(start=first, end=last)
    # DTEND gives an exact elapsed duration; all-day / DURATION use nominal local time.
    nominal = all_day or "DURATION" in event
    duration = end - start if nominal else last.astimezone(UTC) - first.astimezone(UTC)
    if duration <= timedelta():
        raise ValueError("VEVENT duration must be positive")
    occurrences = {first.astimezone(UTC): first}
    if "RRULE" in event:
        rule = event["RRULE"]
        if isinstance(rule, list):
            raise ValueError("multiple recurrence RRULEs are unsupported")
        count = rule.get("COUNT", [None])[0]
        text = ";".join(
            part
            for part in rule.to_ical().decode().split(";")
            if not part.startswith("COUNT=")
        )
        if count is not None and (count < 1 or "UNTIL" in rule):
            raise ValueError(
                "recurrence COUNT must be positive and cannot combine with UNTIL"
            )
        try:
            iterator = rrulestr(text, dtstart=first)
            accepted = 0
            for index, occurrence in enumerate(iterator):
                if index >= max_occurrences:
                    raise ValueError("recurrence expansion limit exceeded")
                if occurrence.astimezone(UTC) >= horizon.end:
                    break
                # RFC 5545: nonexistent local instances neither occur nor count.
                if not datetime_exists(occurrence):
                    continue
                accepted += 1
                occurrences[occurrence.astimezone(UTC)] = occurrence
                if count is not None and accepted >= count:
                    break
        except (TypeError, OverflowError, ValueError) as exc:
            raise ValueError(f"invalid recurrence: {exc}") from exc

    def dates(key):
        properties = event.get(key, [])
        if not isinstance(properties, list):
            properties = [properties]
        values = []
        for prop in properties:
            for value in prop.dts:
                if (type(value.dt) is date) != all_day:
                    raise ValueError(f"{key} must match DTSTART value type")
                values.append(local(value.dt))
                if len(values) > max_occurrences:
                    raise ValueError("recurrence expansion limit exceeded")
        return values

    for occurrence in dates("RDATE"):
        occurrences[occurrence.astimezone(UTC)] = occurrence
    excluded = {value.astimezone(UTC) for value in dates("EXDATE")}
    for instant, occurrence in sorted(occurrences.items()):
        if instant in excluded or not datetime_exists(occurrence):
            continue
        end = occurrence + duration if nominal else instant + duration
        if not datetime_exists(end):
            raise ValueError("VEVENT ends at a nonexistent local time")
        period = Period(start=occurrence, end=end)
        if horizon:
            if period.end <= horizon.start or period.start >= horizon.end:
                continue
            period = Period(
                start=max(period.start, horizon.start), end=min(period.end, horizon.end)
            )
        yield period
