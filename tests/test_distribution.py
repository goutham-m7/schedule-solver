from importlib.metadata import metadata, version

from schedule_solver.api import app


def test_package_and_openapi_versions_match_release():
    assert version("schedule-solver") == "0.2.0"
    assert app.openapi()["info"]["version"] == version("schedule-solver")
    assert metadata("schedule-solver")["License-Expression"] == "MIT"
