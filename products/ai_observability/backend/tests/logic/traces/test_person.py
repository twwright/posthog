import json
from datetime import timedelta
from pathlib import Path
from typing import Any

from parameterized import parameterized

from products.ai_observability.backend.logic.traces.person import person_label, trace_distinct_id
from products.ai_observability.backend.logic.traces.trace_queries import PersonRow

from .rows import T0, make_row

# The case file names each person by the distinct id of the events that carry it, which is what this rule returns.
CASES: list[dict[str, Any]] = json.loads(
    (Path(__file__).parents[4] / "shared" / "trace_expression_cases.json").read_text()
)


@parameterized.expand(
    [
        (
            "the trace event wins over earlier events",
            [
                {"distinct_id": "span-user"},
                {"event": "$ai_trace", "distinct_id": "trace-user", "timestamp": T0 + timedelta(seconds=1)},
            ],
            "trace-user",
        ),
        (
            "otherwise the earliest event",
            [{"distinct_id": "late", "timestamp": T0 + timedelta(seconds=1)}, {"distinct_id": "early"}],
            "early",
        ),
        (
            "empty distinct ids are skipped",
            [
                {"event": "$ai_trace", "distinct_id": ""},
                {"distinct_id": "span-user", "timestamp": T0 + timedelta(seconds=1)},
            ],
            "span-user",
        ),
        ("no distinct id", [{"distinct_id": ""}], None),
    ]
)
def test_trace_distinct_id(_name: str, rows: list[dict[str, Any]], expected: str | None) -> None:
    assert trace_distinct_id([make_row(**row) for row in rows]) == expected


@parameterized.expand([(case["name"], case) for case in CASES])
def test_trace_distinct_id_matches_the_shared_cases(_name: str, case: dict[str, Any]) -> None:
    rows = [
        make_row(
            event=event["event"],
            timestamp=T0 + timedelta(seconds=event.get("second", index)),
            distinct_id=event.get("distinct_id", "user-1"),
        )
        for index, event in enumerate(case["events"])
    ]

    assert trace_distinct_id(rows) == case["person"]


@parameterized.expand(
    [
        ("the display name", "Ada", "Ada"),
        ("the distinct id without one", None, "user-1"),
    ]
)
def test_person_label(_name: str, display_name: str | None, expected: str) -> None:
    assert person_label(PersonRow(distinct_id="user-1", display_name=display_name)) == expected
