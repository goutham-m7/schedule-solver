from datetime import datetime, timezone

import pytest

from schedule_solver.calendars import import_ics, legal_starts, static_reasons
from schedule_solver.models import Workload
from conftest import ts


def test_free_busy_buffers_and_half_open_edges(payload):
    payload["people"][0].update(buffer_before_minutes=15, buffer_after_minutes=15,
        busy=[{"start": ts(10).isoformat(), "end": ts(10, 30).isoformat()}])
    w = Workload.model_validate(payload)
    assert legal_starts(w, w.requests[0], w.people[0]) == [1, 7, 8, 9]


def test_local_working_hours_dst(payload):
    payload.update(start="2027-03-15T12:00:00Z", end="2027-03-15T15:00:00Z")
    payload["people"][0].update(timezone="America/New_York", availability=[
        {"start": payload["start"], "end": payload["end"]}])
    payload["requests"][0].update(earliest=payload["start"], latest=payload["end"])
    w = Workload.model_validate(payload)
    assert legal_starts(w, w.requests[0], w.people[0])[0] == 4
    assert "working_hours:ada" in static_reasons(w, w.requests[0], w.people[0], 0)


def test_ics_tzid_and_all_day():
    text = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:1
DTSTART;TZID=America/New_York:20270104T100000
DTEND;TZID=America/New_York:20270104T110000
END:VEVENT
BEGIN:VEVENT
UID:2
DTSTART;VALUE=DATE:20270105
DTEND;VALUE=DATE:20270106
END:VEVENT
END:VCALENDAR
"""
    periods = import_ics(text, "America/New_York")
    assert periods[0].start == datetime(2027, 1, 4, 15, tzinfo=timezone.utc)
    assert (periods[1].end - periods[1].start).total_seconds() == 86400


@pytest.mark.parametrize("extra", ["RRULE:FREQ=DAILY", "RDATE:20270105T100000Z", "EXDATE:20270105T100000Z", "RECURRENCE-ID:20270104T100000Z"])
def test_ics_recurrence_rejected(extra):
    with pytest.raises(ValueError, match="recurr"):
        import_ics(f"BEGIN:VCALENDAR\nBEGIN:VEVENT\nDTSTART:20270104T100000Z\nDTEND:20270104T110000Z\n{extra}\nEND:VEVENT\nEND:VCALENDAR", "UTC")


def test_ics_floating_rejected():
    with pytest.raises(ValueError, match="floating"):
        import_ics("BEGIN:VCALENDAR\nBEGIN:VEVENT\nDTSTART:20270104T100000\nDTEND:20270104T110000\nEND:VEVENT\nEND:VCALENDAR", "UTC")
