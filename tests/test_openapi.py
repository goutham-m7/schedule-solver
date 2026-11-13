from schedule_solver.api import app


def test_openapi_documents_result_and_incremental_contracts():
    schema = app.openapi()
    result = {"$ref": "#/components/schemas/Result"}
    for path in ("/solve", "/resolve"):
        assert (
            schema["paths"][path]["post"]["responses"]["200"]["content"][
                "application/json"
            ]["schema"]
            == result
        )
    assert schema["components"]["schemas"]["ResolveInput"]["properties"]["previous"][
        "items"
    ] == {"$ref": "#/components/schemas/Meeting"}
    assert (
        "text/calendar"
        in schema["paths"]["/export-ics"]["post"]["responses"]["200"]["content"]
    )
