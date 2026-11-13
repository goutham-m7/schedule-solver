from datetime import UTC, datetime

import pytest

from schedule_solver.calendars import import_ics
from schedule_solver.models import Period


def calendar(start, end, extra):
    return f"BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\nUID:series\nDTSTART{start}\nDTEND{end}\n{extra}\nEND:VEVENT\nEND:VCALENDAR"


def horizon(start="2027-03-07T00:00:00Z", end="2027-03-23T00:00:00Z"):
    return Period(start=start, end=end)


def test_weekly_local_time_survives_dst_with_exdate_and_rdate():
    text = calendar(
        ";TZID=America/New_York:20270307T090000",
        ";TZID=America/New_York:20270307T100000",
        "RRULE:FREQ=WEEKLY;COUNT=3\nEXDATE;TZID=America/New_York:20270321T090000\nRDATE;TZID=America/New_York:20270322T090000",
    )
    periods = import_ics(text, "UTC", horizon())
    assert [p.start.isoformat() for p in periods] == [
        "2027-03-07T14:00:00+00:00",
        "2027-03-14T13:00:00+00:00",
        "2027-03-22T13:00:00+00:00",
    ]


def test_nonexistent_occurrences_are_skipped_and_do_not_count():
    text = calendar(
        ";TZID=America/New_York:20270313T023000",
        ";TZID=America/New_York:20270313T033000",
        "RRULE:FREQ=DAILY;COUNT=3",
    )
    periods = import_ics(text, "UTC", horizon())
    assert [p.start.day for p in periods] == [13, 15, 16]


def test_ambiguous_occurrence_uses_first_fold():
    text = calendar(
        ";TZID=America/New_York:20271106T013000",
        ";TZID=America/New_York:20271106T014500",
        "RRULE:FREQ=DAILY;COUNT=2",
    )
    periods = import_ics(text, "UTC", horizon("2027-11-06T00:00Z", "2027-11-09T00:00Z"))
    assert periods[1].start == datetime(2027, 11, 7, 5, 30, tzinfo=UTC)


def test_all_day_recurrence_uses_local_midnights():
    text = calendar(
        ";VALUE=DATE:20270313",
        ";VALUE=DATE:20270314",
        "RRULE:FREQ=DAILY;COUNT=3\nEXDATE;VALUE=DATE:20270313,20270315",
    )
    periods = import_ics(text, "America/New_York", horizon())
    assert len(periods) == 1
    assert (periods[0].end - periods[0].start).total_seconds() == 23 * 3600


def test_occurrence_overlapping_horizon_is_clipped():
    text = calendar(
        ":20270306T230000Z", ":20270307T010000Z", "RRULE:FREQ=DAILY;COUNT=1"
    )
    periods = import_ics(text, "UTC", horizon())
    assert periods == [Period(start="2027-03-07T00:00Z", end="2027-03-07T01:00Z")]


@pytest.mark.parametrize(
    "extra", ["RECURRENCE-ID:20270307T090000Z", "EXRULE:FREQ=DAILY"]
)
def test_detached_overrides_and_exrule_fail_closed(extra):
    with pytest.raises(ValueError, match="unsupported"):
        import_ics(
            calendar(":20270307T090000Z", ":20270307T100000Z", extra), "UTC", horizon()
        )


def test_historical_expansion_is_bounded():
    text = calendar(":20000101T090000Z", ":20000101T100000Z", "RRULE:FREQ=DAILY")
    with pytest.raises(ValueError, match="expansion limit"):
        import_ics(text, "UTC", horizon(), max_occurrences=10)


def test_invalid_recurrence_fails_closed():
    with pytest.raises(ValueError, match="recurrence"):
        import_ics(
            calendar(":20270307T090000Z", ":20270307T100000Z", "RRULE:FREQ=BOGUS"),
            "UTC",
            horizon(),
        )


def test_rdate_and_exdate_without_rrule():
    text = calendar(
        ":20270307T090000Z",
        ":20270307T100000Z",
        "RDATE:20270308T090000Z,20270309T090000Z\nEXDATE:20270307T090000Z",
    )
    assert [p.start.day for p in import_ics(text, "UTC", horizon())] == [8, 9]
