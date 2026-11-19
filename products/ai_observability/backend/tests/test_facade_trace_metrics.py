from dataclasses import replace
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from posthog.test.base import BaseTest
from unittest.mock import patch

from django.core.cache import cache

from products.ai_observability.backend.facade import api, contracts
from products.ai_observability.backend.logic.traces.trace_metrics import NO_TRACES, PeriodTotals
from products.ai_observability.backend.logic.traces.trace_metrics_queries import (
    TraceMetricsRows,
    TraceMetricsTooHeavyError,
)
from products.ai_observability.backend.logic.traces.trace_selection import TraceSelection, TraceWindow

from .property_access import hide_event_property

DAY = datetime(2026, 10, 5, tzinfo=UTC)
READ = "products.ai_observability.backend.logic.traces.trace_metrics_queries.load_trace_metrics"


def selection_between(start: datetime, end: datetime, *, filter_test_accounts: bool | None = None) -> TraceSelection:
    return TraceSelection(window=TraceWindow(start=start, end=end), filter_test_accounts=filter_test_accounts)


def rows_with(buckets: dict[datetime, PeriodTotals]) -> TraceMetricsRows:
    return TraceMetricsRows(
        current=replace(NO_TRACES, traces=4, errored=1, cost=2.0, users=3), previous=NO_TRACES, buckets=buckets
    )


class TestLoadTraceMetrics(BaseTest):
    def setUp(self) -> None:
        super().setUp()
        cache.clear()

    def test_load_trace_metrics_builds_tiles_and_buckets(self) -> None:
        busy_hour = replace(NO_TRACES, traces=4, errored=1)
        selection = selection_between(DAY, DAY + timedelta(hours=3))

        with patch(READ, return_value=rows_with({DAY + timedelta(hours=1): busy_hour})):
            metrics = api.load_trace_metrics(self.team, self.user, selection)()

        assert metrics.bucket_size == contracts.TraceMetricBucketSize.HOUR
        assert (metrics.previous_date_from, metrics.previous_date_to) == (DAY - timedelta(hours=3), DAY)
        tiles = {tile.key: tile for tile in metrics.tiles}
        assert set(tiles) == set(contracts.TraceMetricKey)
        assert (tiles[contracts.TraceMetricKey.TRACES].value, tiles[contracts.TraceMetricKey.ERROR_RATE].value) == (
            4,
            0.25,
        )
        assert [bucket.start for bucket in metrics.buckets] == [DAY + timedelta(hours=hour) for hour in range(3)]
        assert [bucket.values.traces for bucket in metrics.buckets] == [0, 4, 0]
        assert (metrics.buckets[0].values.error_rate, metrics.buckets[1].values.error_rate) == (None, 0.25)

    def test_load_trace_metrics_reads_once_within_cache_ttl(self) -> None:
        selection = selection_between(DAY, DAY + timedelta(hours=3))

        with patch(READ, return_value=rows_with({})) as read:
            first = api.load_trace_metrics(self.team, self.user, selection)()
            second = api.load_trace_metrics(self.team, self.user, selection)()

        assert read.call_count == 1
        assert first == second

    def test_load_trace_metrics_refuses_a_too_heavy_range_again_without_reading(self) -> None:
        selection = selection_between(DAY, DAY + timedelta(days=90))

        with patch(READ, side_effect=TraceMetricsTooHeavyError()) as read:
            for _ in range(2):
                with pytest.raises(TraceMetricsTooHeavyError):
                    api.load_trace_metrics(self.team, self.user, selection)

        assert read.call_count == 1

    def test_cache_key_rounds_window_to_bucket(self) -> None:
        start, end = DAY + timedelta(minutes=7), DAY + timedelta(hours=3, minutes=7)
        base = selection_between(start, end)
        same_bucket = [selection_between(start + timedelta(minutes=34), end + timedelta(minutes=34))]
        other_bucket = [
            selection_between(start + timedelta(hours=1), end + timedelta(hours=1)),
            selection_between(start, end, filter_test_accounts=True),
            replace(base, include_support_traces=True),
        ]

        with patch(READ, return_value=rows_with({})) as read:
            for selection in [base, *same_bucket, *other_bucket]:
                api.load_trace_metrics(self.team, self.user, selection)

        assert read.call_count == 1 + len(other_bucket)

    def test_cache_key_separates_users_with_different_property_restrictions(self) -> None:
        selection = selection_between(DAY, DAY + timedelta(hours=3))

        with patch(READ, return_value=rows_with({})) as read:
            api.load_trace_metrics(self.team, self.user, selection)
            hide_event_property(self.team, self.user, "secret")
            api.load_trace_metrics(self.team, self.user, selection)

        assert read.call_count == 2

    def test_cache_key_floors_the_window_in_the_project_zone(self) -> None:
        self.team.timezone = "America/Los_Angeles"
        self.team.save()
        zone = ZoneInfo("America/Los_Angeles")
        late_evening = datetime(2026, 10, 5, 23, 58, tzinfo=zone)
        just_after_midnight = datetime(2026, 10, 6, 0, 2, tzinfo=zone)

        with patch(READ, return_value=rows_with({})) as read:
            builds = [
                api.load_trace_metrics(
                    self.team,
                    self.user,
                    selection_between((moment - timedelta(days=3)).astimezone(UTC), moment.astimezone(UTC)),
                )
                for moment in (late_evening, just_after_midnight)
            ]

        assert read.call_count == 2
        assert [build().buckets[-1].start for build in builds] == [
            datetime(2026, 10, 5, tzinfo=zone),
            datetime(2026, 10, 6, tzinfo=zone),
        ]
