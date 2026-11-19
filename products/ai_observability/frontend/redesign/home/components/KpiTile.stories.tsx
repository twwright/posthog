import type { Meta, StoryObj } from '@storybook/react'

import { TraceMetricChangeUnitApi, TraceMetricKeyApi, TraceMetricStatusApi } from '../../../generated/api.schemas'
import { METRICS } from '../homeFixtures'
import { KpiTile } from './KpiTile'

const COST_TILE = METRICS.tiles[0]
const COST_SERIES = METRICS.buckets.map((bucket) => bucket.values.cost)

const meta: Meta<typeof KpiTile> = {
    title: 'Scenes-App/AI observability/Home/KPI tile',
    component: KpiTile,
    parameters: { testOptions: { snapshotBrowsers: [] } },
    args: { tile: COST_TILE, series: COST_SERIES, label: 'Cost', loading: false },
    decorators: [
        (StoryComponent) => (
            <div className="w-48">
                <StoryComponent />
            </div>
        ),
    ],
}
export default meta

type Story = StoryObj<typeof KpiTile>

export const Ok: Story = {}

export const LinkedToList: Story = { args: { to: '/ai-observability/traces' } }

export const NegativePointChange: Story = {
    args: {
        tile: {
            key: TraceMetricKeyApi.ErrorRate,
            value: 0.018,
            previous: 0.022,
            change: -0.4,
            changeUnit: TraceMetricChangeUnitApi.Points,
            status: TraceMetricStatusApi.Ok,
            docsUrl: null,
        },
        label: 'Error rate',
    },
}

export const SecondsChange: Story = {
    args: {
        tile: {
            key: TraceMetricKeyApi.P95Latency,
            value: 4.2,
            previous: 4.5,
            change: -0.3,
            changeUnit: TraceMetricChangeUnitApi.Seconds,
            status: TraceMetricStatusApi.Ok,
            docsUrl: null,
        },
        label: 'p95 latency',
    },
}

export const NoChange: Story = { args: { tile: { ...COST_TILE, previous: null, change: null } } }

export const NoDataInRange: Story = {
    args: { tile: { ...COST_TILE, value: 0, previous: 0, change: null }, series: [0, 0, 0, 0, 0, 0, 0] },
}

export const NotSetUp: Story = {
    args: {
        tile: {
            ...COST_TILE,
            value: null,
            previous: null,
            change: null,
            status: TraceMetricStatusApi.NotSetUp,
            docsUrl: 'https://posthog.com/docs/ai-observability/calculating-costs',
        },
        series: [],
    },
}

export const Loading: Story = { args: { loading: true, series: [] } }
