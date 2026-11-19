import { humanFriendlyNumber, percentage } from 'lib/utils/numbers'

import { type TraceMetricChangeUnitApi, TraceMetricKeyApi } from '../../generated/api.schemas'
import { formatCostUsd } from '../shared/formatCost'
import { formatLatencyMs } from '../trace/components/formatStats'
import { CHANGE_UNIT_SUFFIX } from './tileMeta'

const MINUS = '−'
const NO_VALUE = '-'

function orDash(value: number | null, format: (value: number) => string): string {
    return value === null ? NO_VALUE : format(value)
}

export function formatTileValue(key: TraceMetricKeyApi, value: number | null): string {
    switch (key) {
        case TraceMetricKeyApi.Cost:
            return orDash(value, formatCostUsd)
        case TraceMetricKeyApi.ErrorRate:
            return orDash(value, (fraction) => percentage(fraction, 1))
        case TraceMetricKeyApi.P95Latency:
            return orDash(value, (seconds) => formatLatencyMs(seconds * 1000))
        default:
            return humanFriendlyNumber(value)
    }
}

export function formatTileChange(change: number | null, unit: TraceMetricChangeUnitApi): string {
    return orDash(change, (amount) => {
        const magnitude = humanFriendlyNumber(Math.abs(amount), 1)
        if (magnitude === '0') {
            return `0${CHANGE_UNIT_SUFFIX[unit]}`
        }
        return `${amount < 0 ? MINUS : '+'}${magnitude}${CHANGE_UNIT_SUFFIX[unit]}`
    })
}
