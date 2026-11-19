import {
    AIObservabilityInstrumentationCheckEnumApi,
    InstrumentationCheckStatusEnumApi,
    TraceMetricBucketSizeApi,
    TraceMetricChangeUnitApi,
    TraceMetricKeyApi,
    TraceMetricStatusApi,
    type InstrumentationCheckApi,
    type InstrumentationChecklistApi,
    type TraceMetricsApi,
    type TraceMetricTileApi,
} from '../../generated/api.schemas'

const DAYS = 7
const NOT_SET_UP_DOCS_URL = 'https://posthog.com/docs/ai-observability/installation'

function trend(base: number, step: number): number[] {
    return Array.from({ length: DAYS }, (_, index) => base + step * index + (index % 2) * step)
}

export const RANGE_TOO_LONG_DETAIL = 'This range is too long to compute. Try a shorter one.'

const OK_TILES: TraceMetricTileApi[] = [
    {
        key: TraceMetricKeyApi.Cost,
        value: 1204,
        previous: 1075,
        change: 12,
        changeUnit: TraceMetricChangeUnitApi.Percent,
        status: TraceMetricStatusApi.Ok,
        docsUrl: null,
    },
    {
        key: TraceMetricKeyApi.Users,
        value: 3410,
        previous: 3279,
        change: 4,
        changeUnit: TraceMetricChangeUnitApi.Percent,
        status: TraceMetricStatusApi.Ok,
        docsUrl: null,
    },
    {
        key: TraceMetricKeyApi.Sessions,
        value: 8120,
        previous: 8300,
        change: -2.2,
        changeUnit: TraceMetricChangeUnitApi.Percent,
        status: TraceMetricStatusApi.Ok,
        docsUrl: null,
    },
    {
        key: TraceMetricKeyApi.Traces,
        value: 52118,
        previous: 47810,
        change: 9,
        changeUnit: TraceMetricChangeUnitApi.Percent,
        status: TraceMetricStatusApi.Ok,
        docsUrl: null,
    },
    {
        key: TraceMetricKeyApi.ErrorRate,
        value: 0.018,
        previous: 0.022,
        change: -0.4,
        changeUnit: TraceMetricChangeUnitApi.Points,
        status: TraceMetricStatusApi.Ok,
        docsUrl: null,
    },
    {
        key: TraceMetricKeyApi.P95Latency,
        value: 4.2,
        previous: 4.5,
        change: -0.3,
        changeUnit: TraceMetricChangeUnitApi.Seconds,
        status: TraceMetricStatusApi.Ok,
        docsUrl: null,
    },
]

function metricsOf(tiles: TraceMetricTileApi[]): TraceMetricsApi {
    const cost = trend(120, 25)
    const users = trend(400, 40)
    const sessions = trend(1000, 60)
    const traces = trend(6000, 500)
    const errorRate = trend(0.03, -0.002)
    const p95Latency = trend(3.6, 0.2)
    return {
        dateFrom: '2026-11-12T00:00:00Z',
        dateTo: '2026-11-19T00:00:00Z',
        previousDateFrom: '2026-11-05T00:00:00Z',
        previousDateTo: '2026-11-12T00:00:00Z',
        bucketSize: TraceMetricBucketSizeApi.Day,
        tiles,
        buckets: Array.from({ length: DAYS }, (_, index) => ({
            start: `2026-11-${String(12 + index).padStart(2, '0')}T00:00:00Z`,
            values: {
                cost: cost[index],
                users: users[index],
                sessions: sessions[index],
                traces: traces[index],
                errorRate: errorRate[index],
                p95Latency: p95Latency[index],
            },
        })),
    }
}

export const METRICS: TraceMetricsApi = metricsOf(OK_TILES)

export const METRICS_NOT_SET_UP: TraceMetricsApi = metricsOf(
    OK_TILES.map((tile) =>
        tile.key === TraceMetricKeyApi.Traces || tile.key === TraceMetricKeyApi.ErrorRate
            ? tile
            : {
                  ...tile,
                  value: null,
                  previous: null,
                  change: null,
                  status: TraceMetricStatusApi.NotSetUp,
                  docsUrl: NOT_SET_UP_DOCS_URL,
              }
    )
)

export const TILE_LINKS: Partial<Record<TraceMetricKeyApi, string>> = {
    [TraceMetricKeyApi.Traces]: '/ai-observability/traces',
    [TraceMetricKeyApi.ErrorRate]: '/ai-observability/errors',
}

const CHECKLIST_DOCS_URL = 'https://posthog.com/docs/ai-observability/installation'

function check(
    key: AIObservabilityInstrumentationCheckEnumApi,
    title: string,
    status: InstrumentationCheckStatusEnumApi,
    detail: string
): InstrumentationCheckApi {
    return { key, status, title, detail, docs_url: CHECKLIST_DOCS_URL, stats: {} }
}

const { Sessions, ToolCalls, UserIdentity, TraceStructure } = AIObservabilityInstrumentationCheckEnumApi
const { Ok, Warning, Dismissed } = InstrumentationCheckStatusEnumApi

export const CHECKLIST_ALL_OK: InstrumentationChecklistApi = {
    window_days: 30,
    agent_prompt: null,
    passing: 4,
    total: 4,
    checks: [
        check(Sessions, 'Sessions', Ok, 'Generations carry a session id.'),
        check(ToolCalls, 'Tool calls', Ok, 'Tool calls appear in traces.'),
        check(UserIdentity, 'User identity', Ok, 'Generations carry a distinct id.'),
        check(TraceStructure, 'Trace structure', Ok, 'Spans nest under their traces.'),
    ],
}

export const CHECKLIST_WARNING: InstrumentationChecklistApi = {
    window_days: 30,
    agent_prompt: 'Add a session id to every generation. Docs: https://posthog.com/docs/ai-observability/installation',
    passing: 3,
    total: 4,
    checks: [
        check(Sessions, 'Sessions', Warning, 'No generations carry a session id. Send $ai_session_id.'),
        check(ToolCalls, 'Tool calls', Ok, 'Tool calls appear in traces.'),
        check(UserIdentity, 'User identity', Dismissed, 'Marked as not applicable.'),
        check(TraceStructure, 'Trace structure', Ok, 'Spans nest under their traces.'),
    ],
}

export const CHECKLIST_DISMISSED: InstrumentationChecklistApi = {
    window_days: 30,
    agent_prompt: null,
    passing: 4,
    total: 4,
    checks: [
        check(Sessions, 'Sessions', Dismissed, 'Marked as not applicable.'),
        check(ToolCalls, 'Tool calls', Ok, 'Tool calls appear in traces.'),
        check(UserIdentity, 'User identity', Ok, 'Generations carry a distinct id.'),
        check(TraceStructure, 'Trace structure', Ok, 'Spans nest under their traces.'),
    ],
}
