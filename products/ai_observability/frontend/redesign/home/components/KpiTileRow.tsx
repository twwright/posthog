import {
    TraceMetricChangeUnitApi,
    type TraceMetricKeyApi,
    TraceMetricStatusApi,
    type TraceMetricsApi,
} from '../../../generated/api.schemas'
import { TILE_KEYS, TILE_META } from '../tileMeta'
import { KpiTile } from './KpiTile'

export interface KpiTileRowProps {
    metrics: TraceMetricsApi | null
    loading: boolean
    links: Partial<Record<TraceMetricKeyApi, string>>
}

function TileGrid({ children }: { children: React.ReactNode }): JSX.Element {
    return (
        <div className="@container">
            <div className="grid grid-cols-2 gap-2 @2xl:grid-cols-3 @5xl:grid-cols-6">{children}</div>
        </div>
    )
}

export function KpiTileRow({ metrics, loading, links }: KpiTileRowProps): JSX.Element | null {
    if (loading) {
        return (
            <TileGrid>
                {TILE_KEYS.map((key) => (
                    <KpiTile
                        key={key}
                        tile={{
                            key,
                            value: null,
                            previous: null,
                            change: null,
                            changeUnit: TraceMetricChangeUnitApi.Percent,
                            status: TraceMetricStatusApi.Ok,
                            docsUrl: null,
                        }}
                        series={[]}
                        label={TILE_META[key].label}
                        loading
                    />
                ))}
            </TileGrid>
        )
    }
    if (metrics === null) {
        return null
    }
    return (
        <TileGrid>
            {metrics.tiles.map((tile) => {
                const { label, valuesField } = TILE_META[tile.key]
                return (
                    <KpiTile
                        key={tile.key}
                        tile={tile}
                        series={metrics.buckets.map((bucket) => bucket.values[valuesField])}
                        label={label}
                        to={links[tile.key]}
                        loading={false}
                    />
                )
            })}
        </TileGrid>
    )
}
