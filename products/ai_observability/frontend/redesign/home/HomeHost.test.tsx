import { cleanup, render, waitFor } from '@testing-library/react'
import { router } from 'kea-router'

import { urls } from 'scenes/urls'

import { resumeKeaLoadersErrors, silenceKeaLoadersErrors } from '~/initKea'
import { useMocks } from '~/mocks/jest'
import { initKeaTests } from '~/test/init'

import { CHECKLIST_WARNING, METRICS } from './homeFixtures'
import { HomeHost } from './HomeHost'

type Answer = [number, unknown]

describe('HomeHost', () => {
    let metricsAnswer: Answer

    beforeEach(() => {
        metricsAnswer = [200, METRICS]
        useMocks({
            get: {
                '/api/projects/:team_id/ai_observability/traces/metrics/': () => metricsAnswer,
                '/api/projects/:team_id/ai_observability/instrumentation_checklist/': () => [200, CHECKLIST_WARNING],
                '/api/projects/:team_id/dashboards/': () => [200, { count: 1, results: [{ id: 42 }] }],
            },
        })
        initKeaTests()
        router.actions.push(urls.aiObservabilityDashboard())
    })

    afterEach(() => {
        cleanup()
        resumeKeaLoadersErrors()
    })

    it('renders tiles, the four placeholders and the old dashboard link', async () => {
        const { container } = render(<HomeHost />)

        await waitFor(() => expect(container.textContent).toContain('52,118'))
        await waitFor(() => expect(container.querySelector('[data-attr="home-open-dashboard"]')).not.toBeNull())
        expect(container.querySelectorAll('[data-attr^="home-tile-"]')).toHaveLength(6)
        expect(container.querySelectorAll('[data-attr^="home-section-"]')).toHaveLength(4)
        await waitFor(() => expect(container.querySelector('[data-attr="home-instrumentation"]')).not.toBeNull())
    })

    it('shows the range banner for a range that is too long', async () => {
        silenceKeaLoadersErrors()
        metricsAnswer = [422, { detail: 'Pick a range of 90 days or less.', code: 'range_too_long' }]

        const view = render(<HomeHost />)

        expect(await view.findByText('Pick a range of 90 days or less.')).toBeTruthy()
        expect(view.container.querySelectorAll('[data-attr^="home-tile-"]')).toHaveLength(0)
    })

    it('shows a retry for any other failure', async () => {
        silenceKeaLoadersErrors()
        metricsAnswer = [500, { detail: 'boom' }]

        const view = render(<HomeHost />)

        expect(await view.findByText('Could not load the metrics')).toBeTruthy()
        expect(view.container.querySelector('[data-attr="home-metrics-retry"]')).not.toBeNull()
    })
})
