import { cleanup, render } from '@testing-library/react'

import { initKeaTests } from '~/test/init'

import {
    TraceMetricChangeUnitApi,
    TraceMetricKeyApi,
    TraceMetricStatusApi,
    type TraceMetricTileApi,
} from '../../../generated/api.schemas'
import { KpiTile } from './KpiTile'

const DOCS_URL = 'https://posthog.com/docs/ai-observability/installation'

function tileOf(overrides: Partial<TraceMetricTileApi>): TraceMetricTileApi {
    return {
        key: TraceMetricKeyApi.Cost,
        value: 1204,
        previous: 1075,
        change: 12,
        changeUnit: TraceMetricChangeUnitApi.Percent,
        status: TraceMetricStatusApi.Ok,
        docsUrl: null,
        ...overrides,
    }
}

function shownNumbers(container: HTMLElement, attr: string): string[] {
    return Array.from(container.querySelectorAll(`[data-attr="${attr}"] [translate="no"]`)).map(
        (element) => element.textContent ?? ''
    )
}

describe('KpiTile', () => {
    beforeEach(() => initKeaTests())
    afterEach(cleanup)

    it('shows Not set up linked to docs when status is not_set_up', () => {
        const { container } = render(
            <KpiTile
                tile={tileOf({
                    key: TraceMetricKeyApi.ErrorRate,
                    value: null,
                    change: null,
                    status: TraceMetricStatusApi.NotSetUp,
                    docsUrl: DOCS_URL,
                })}
                series={[]}
                label="Error rate"
                loading={false}
            />
        )

        const link = container.querySelector('[data-attr="home-tile-error-rate-not-set-up"]')
        expect(link?.textContent).toContain('Not set up')
        expect(link?.getAttribute('href')).toBe(DOCS_URL)
    })

    it.each<[string, Partial<TraceMetricTileApi>, string, string]>([
        ['percent', {}, '$1,204.00', '+12%'],
        ['negative percent', { change: -4.2 }, '$1,204.00', '−4.2%'],
        ['sub-cent cost', { value: 0.004 }, '$0.004', '+12%'],
        [
            'points',
            {
                key: TraceMetricKeyApi.ErrorRate,
                value: 0.018,
                change: -0.4,
                changeUnit: TraceMetricChangeUnitApi.Points,
            },
            '1.8%',
            '−0.4 pt',
        ],
        [
            'seconds',
            {
                key: TraceMetricKeyApi.P95Latency,
                value: 4.2,
                change: -0.3,
                changeUnit: TraceMetricChangeUnitApi.Seconds,
            },
            '4.2s',
            '−0.3s',
        ],
        ['count', { key: TraceMetricKeyApi.Traces, value: 52118, change: 9 }, '52,118', '+9%'],
        ['no change', { change: null }, '$1,204.00', '-'],
    ])('formats value and change by unit: %s', (_name, overrides, value, change) => {
        const tile = tileOf(overrides)
        const slug = tile.key.replaceAll('_', '-')
        const { container } = render(<KpiTile tile={tile} series={[1, 2, 3]} label="Label" loading={false} />)

        expect(shownNumbers(container, `home-tile-${slug}`)).toEqual([value, change])
    })

    it('shows a skeleton while loading, not zero', () => {
        const { container } = render(<KpiTile tile={tileOf({ value: 0 })} series={[]} label="Cost" loading />)

        expect(container.querySelector('.LemonSkeleton')).not.toBeNull()
        expect(container.textContent).not.toContain('0')
        expect(container.textContent).toContain('Cost')
    })
})
