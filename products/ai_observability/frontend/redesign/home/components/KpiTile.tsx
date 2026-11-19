import { LemonSkeleton, Link } from '@posthog/lemon-ui'

import { TraceMetricStatusApi, type TraceMetricTileApi } from '../../../generated/api.schemas'
import { formatTileChange, formatTileValue } from '../formatTile'
import { tileSlug } from '../tileMeta'
import { KpiTileSparkline } from './KpiTileSparkline'

export interface KpiTileProps {
    tile: TraceMetricTileApi
    series: (number | null)[]
    label: string
    to?: string
    loading: boolean
}

function NotSetUp({ slug, docsUrl }: { slug: string; docsUrl: string | null }): JSX.Element {
    // pinned: data-attrs feed autocapture; dashboards and tests find the status by this value
    const dataAttr = `home-tile-${slug}-not-set-up`
    return docsUrl ? (
        <Link to={docsUrl} target="_blank" className="text-base font-semibold" data-attr={dataAttr}>
            Not set up
        </Link>
    ) : (
        <span className="text-base font-semibold text-secondary" data-attr={dataAttr}>
            Not set up
        </span>
    )
}

export function KpiTile({ tile, series, label, to, loading }: KpiTileProps): JSX.Element {
    const slug = tileSlug(tile.key)
    const notSetUp = !loading && tile.status === TraceMetricStatusApi.NotSetUp
    return (
        // pinned: data-attrs feed autocapture; dashboards and tests find the tile by this value
        <div
            className="flex min-w-0 flex-col gap-1 rounded border bg-surface-primary p-3"
            data-attr={`home-tile-${slug}`}
        >
            {to ? (
                <Link to={to} subtle className="text-xs font-medium text-secondary">
                    {label}
                </Link>
            ) : (
                <span className="text-xs font-medium text-secondary">{label}</span>
            )}
            {loading ? (
                <>
                    <LemonSkeleton className="h-7 w-2/3" />
                    <LemonSkeleton className="h-8 w-full" />
                    <LemonSkeleton className="h-4 w-1/3" />
                </>
            ) : notSetUp ? (
                <NotSetUp slug={slug} docsUrl={tile.docsUrl} />
            ) : (
                <>
                    <span className="truncate text-2xl font-semibold tabular-nums" translate="no">
                        {formatTileValue(tile.key, tile.value)}
                    </span>
                    <div className="h-8">{series.length > 0 ? <KpiTileSparkline series={series} /> : null}</div>
                    <span className="text-xs tabular-nums text-secondary" translate="no">
                        {formatTileChange(tile.change, tile.changeUnit)}
                    </span>
                </>
            )}
        </div>
    )
}
