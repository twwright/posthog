import { cleanup, fireEvent, render } from '@testing-library/react'

import { initKeaTests } from '~/test/init'

import { CHECKLIST_ALL_OK, CHECKLIST_DISMISSED, CHECKLIST_WARNING } from '../homeFixtures'
import { InstrumentationRow, InstrumentationRowProps } from './InstrumentationRow'

function renderRow(props: Partial<InstrumentationRowProps> = {}): ReturnType<typeof render> {
    return render(
        <InstrumentationRow
            checklist={CHECKLIST_WARNING}
            loading={false}
            onDismiss={jest.fn()}
            onRestore={jest.fn()}
            {...props}
        />
    )
}

describe('InstrumentationRow', () => {
    beforeEach(() => {
        initKeaTests()
    })

    afterEach(cleanup)

    it('shows the passing count the server reports', () => {
        const { container } = renderRow({ checklist: { ...CHECKLIST_DISMISSED, passing: 1, total: 7 } })

        expect(container.querySelector('[data-attr="home-instrumentation-toggle"]')?.textContent).toContain(
            'Instrumentation 1 of 7'
        )
    })

    it('starts closed when nothing warns and opens on toggle', () => {
        const { container } = renderRow({ checklist: CHECKLIST_ALL_OK })
        expect(container.textContent).not.toContain('Generations carry a session id.')

        fireEvent.click(container.querySelector('[data-attr="home-instrumentation-toggle"]') as HTMLElement)

        expect(container.textContent).toContain('Generations carry a session id.')
    })

    it('starts open when a check warns, with dismiss and restore per check', () => {
        const onDismiss = jest.fn()
        const onRestore = jest.fn()
        const { container } = renderRow({ onDismiss, onRestore })

        expect(container.textContent).toContain('No generations carry a session id.')
        fireEvent.click(container.querySelector('[data-attr="home-instrumentation-dismiss-sessions"]') as HTMLElement)
        fireEvent.click(
            container.querySelector('[data-attr="home-instrumentation-restore-user_identity"]') as HTMLElement
        )

        expect(onDismiss).toHaveBeenCalledWith('sessions')
        expect(onRestore).toHaveBeenCalledWith('user_identity')
    })

    it('shows the agent prompt button only when there is a prompt', () => {
        const withPrompt = renderRow()
        expect(withPrompt.container.querySelector('[data-attr="home-instrumentation-prompt"]')).not.toBeNull()
        cleanup()

        const withoutPrompt = renderRow({ checklist: { ...CHECKLIST_WARNING, agent_prompt: null } })
        expect(withoutPrompt.container.querySelector('[data-attr="home-instrumentation-prompt"]')).toBeNull()
    })

    it('renders nothing once loading ends without a checklist', () => {
        const { container } = renderRow({ checklist: null })

        expect(container.querySelector('[data-attr="home-instrumentation"]')).toBeNull()
    })
})
