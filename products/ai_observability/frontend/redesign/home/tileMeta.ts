import { TraceMetricChangeUnitApi, TraceMetricKeyApi, type TraceMetricValuesApi } from '../../generated/api.schemas'

interface TileMeta {
    label: string
    valuesField: keyof TraceMetricValuesApi
}

export const TILE_KEYS: TraceMetricKeyApi[] = [
    TraceMetricKeyApi.Cost,
    TraceMetricKeyApi.Users,
    TraceMetricKeyApi.Sessions,
    TraceMetricKeyApi.Traces,
    TraceMetricKeyApi.ErrorRate,
    TraceMetricKeyApi.P95Latency,
]

export const TILE_META: Record<TraceMetricKeyApi, TileMeta> = {
    [TraceMetricKeyApi.Cost]: { label: 'Cost', valuesField: 'cost' },
    [TraceMetricKeyApi.Users]: { label: 'Users', valuesField: 'users' },
    [TraceMetricKeyApi.Sessions]: { label: 'Sessions', valuesField: 'sessions' },
    [TraceMetricKeyApi.Traces]: { label: 'Traces', valuesField: 'traces' },
    [TraceMetricKeyApi.ErrorRate]: {
        label: 'Error rate',
        valuesField: 'errorRate',
    },
    [TraceMetricKeyApi.P95Latency]: {
        label: 'p95 latency',
        valuesField: 'p95Latency',
    },
}

export function tileSlug(key: TraceMetricKeyApi): string {
    return key.replaceAll('_', '-')
}

export const CHANGE_UNIT_SUFFIX: Record<TraceMetricChangeUnitApi, string> = {
    [TraceMetricChangeUnitApi.Percent]: '%',
    [TraceMetricChangeUnitApi.Points]: ' pt',
    [TraceMetricChangeUnitApi.Seconds]: ' s',
}
