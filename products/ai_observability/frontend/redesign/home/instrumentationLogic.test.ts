import { expectLogic } from 'kea-test-utils'

import { resumeKeaLoadersErrors, silenceKeaLoadersErrors } from '~/initKea'
import { useMocks } from '~/mocks/jest'
import { initKeaTests } from '~/test/init'

import { AIObservabilityInstrumentationCheckEnumApi } from '../../generated/api.schemas'
import { CHECKLIST_ALL_OK, CHECKLIST_WARNING } from './homeFixtures'
import { instrumentationLogic } from './instrumentationLogic'

const BASE_URL = '/api/projects/:team_id/ai_observability/instrumentation_checklist/'

describe('instrumentationLogic', () => {
    let logic: ReturnType<typeof instrumentationLogic.build>
    let dismissBodies: unknown[]
    let restoreBodies: unknown[]

    beforeEach(() => {
        dismissBodies = []
        restoreBodies = []
        useMocks({
            get: { [BASE_URL]: () => [200, CHECKLIST_WARNING] },
            post: {
                [`${BASE_URL}dismiss/`]: async ({ request }) => {
                    dismissBodies.push(await request.json())
                    return [200, CHECKLIST_ALL_OK]
                },
                [`${BASE_URL}restore/`]: async ({ request }) => {
                    restoreBodies.push(await request.json())
                    return [200, CHECKLIST_WARNING]
                },
            },
        })
        initKeaTests()
        logic = instrumentationLogic()
        logic.mount()
    })

    afterEach(() => {
        resumeKeaLoadersErrors()
    })

    it('dismiss posts the check and installs the recomputed checklist', async () => {
        await expectLogic(logic).toFinishAllListeners()

        logic.actions.dismiss(AIObservabilityInstrumentationCheckEnumApi.Sessions)
        await expectLogic(logic).toFinishAllListeners()

        expect(dismissBodies).toEqual([{ check: 'sessions' }])
        expect(logic.values.checklist).toEqual(CHECKLIST_ALL_OK)
    })

    it('restore posts the check and installs the recomputed checklist', async () => {
        await expectLogic(logic).toFinishAllListeners()

        logic.actions.restore(AIObservabilityInstrumentationCheckEnumApi.UserIdentity)
        await expectLogic(logic).toFinishAllListeners()

        expect(restoreBodies).toEqual([{ check: 'user_identity' }])
        expect(logic.values.checklist).toEqual(CHECKLIST_WARNING)
    })

    it('keeps the checklist when a dismiss fails', async () => {
        await expectLogic(logic).toFinishAllListeners()
        silenceKeaLoadersErrors()
        useMocks({ post: { [`${BASE_URL}dismiss/`]: () => [500, { detail: 'boom' }] } })

        logic.actions.dismiss(AIObservabilityInstrumentationCheckEnumApi.Sessions)
        await expectLogic(logic).toFinishAllListeners()

        expect(logic.values.checklist).toEqual(CHECKLIST_WARNING)
        expect(logic.values.checklistLoading).toBe(false)
    })
})
