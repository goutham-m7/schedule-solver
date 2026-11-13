from datetime import UTC, datetime

import pytest


def ts(hour, minute=0, day=4):
    return datetime(2027, 1, day, hour, minute, tzinfo=UTC)


@pytest.fixture
def payload():
    return {
        "start": ts(9).isoformat(),
        "end": ts(12).isoformat(),
        "grid_minutes": 15,
        "people": [
            {
                "id": "ada",
                "timezone": "UTC",
                "skills": ["python"],
                "roles": ["reviewer"],
                "availability": [
                    {"start": ts(9).isoformat(), "end": ts(12).isoformat()}
                ],
            }
        ],
        "requests": [
            {
                "id": "review",
                "duration_minutes": 30,
                "earliest": ts(9).isoformat(),
                "latest": ts(12).isoformat(),
                "required_attendees": ["ada"],
            }
        ],
    }
