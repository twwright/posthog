import { ReactNode } from 'react'

import { HomeSectionPlaceholder } from './HomeSectionPlaceholder'

export interface HomeLayoutProps {
    tiles: ReactNode
    instrumentation: ReactNode
    toolbar: ReactNode
}

export function HomeLayout({ tiles, instrumentation, toolbar }: HomeLayoutProps): JSX.Element {
    return (
        <div className="@container flex min-w-0 flex-col gap-4">
            <div className="flex flex-wrap items-center justify-between gap-2">{toolbar}</div>
            {tiles}
            {instrumentation}
            <div className="grid grid-cols-1 gap-4 @3xl:grid-cols-2">
                <HomeSectionPlaceholder section="to-review" title="To review" switchLabels={['Sessions', 'Traces']} />
                <HomeSectionPlaceholder section="evals" title="Evals to inspect" />
                <HomeSectionPlaceholder section="expensive-users" title="Most expensive users" />
                <HomeSectionPlaceholder section="topics" title="Top topics" />
            </div>
        </div>
    )
}
