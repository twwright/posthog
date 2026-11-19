import type { Meta, StoryObj } from '@storybook/react'

import { CHECKLIST_ALL_OK, CHECKLIST_DISMISSED, CHECKLIST_WARNING } from '../homeFixtures'
import { InstrumentationRow } from './InstrumentationRow'

const meta: Meta<typeof InstrumentationRow> = {
    title: 'Scenes-App/AI observability/Home/Instrumentation row',
    component: InstrumentationRow,
    parameters: { testOptions: { snapshotBrowsers: [] } },
    args: { checklist: CHECKLIST_ALL_OK, loading: false, onDismiss: () => {}, onRestore: () => {} },
}
export default meta

type Story = StoryObj<typeof InstrumentationRow>

export const AllOkCollapsed: Story = {}

export const WarningOpenWithPrompt: Story = { args: { checklist: CHECKLIST_WARNING } }

export const Dismissed: Story = { args: { checklist: CHECKLIST_DISMISSED } }

export const Loading: Story = { args: { checklist: null, loading: true } }
