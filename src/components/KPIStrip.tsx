import KPICard from './KPICard';

interface KPIStripProps {
    stats: {
        medianSale: number;
        medianRent: number;
        totalActive: number;
        new7d: number;
        saleTrend?: number;
        rentTrend?: number;
    };
    variant?: 'default' | 'home';
    className?: string;
}

function formatPrice(price: number): string {
    if (!price || price === 0) return 'N/A';
    return '$' + Math.round(price).toLocaleString('en-US');
}

export default function KPIStrip({
    stats,
    variant = 'default',
    className = '',
}: KPIStripProps) {
    const wrapperClassName = ['mb-8', className].filter(Boolean).join(' ');
    const gridClassName =
        variant === 'home'
            ? 'grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 lg:gap-5'
            : 'grid grid-cols-2 md:grid-cols-4 gap-5';
    const activeLabel = variant === 'home' ? 'PROPIEDADES ACTIVAS' : 'ACTIVOS HOY';

    return (
        <div className={wrapperClassName}>
            <div className={gridClassName}>
                <KPICard
                    label="PRECIO MEDIO VENTA"
                    value={formatPrice(stats.medianSale)}
                    trend={stats.saleTrend}
                    trendDirection={stats.saleTrend && stats.saleTrend > 0 ? 'up' : stats.saleTrend && stats.saleTrend < 0 ? 'down' : 'neutral'}
                    variant={variant}
                />

                <KPICard
                    label="RENTA MEDIA MENSUAL"
                    value={formatPrice(stats.medianRent)}
                    trend={stats.rentTrend}
                    trendDirection={stats.rentTrend && stats.rentTrend > 0 ? 'up' : stats.rentTrend && stats.rentTrend < 0 ? 'down' : 'neutral'}
                    variant={variant}
                />

                <KPICard
                    label={activeLabel}
                    value={stats.totalActive.toLocaleString()}
                    variant={variant}
                />

                <KPICard
                    label="NUEVOS (7 DIAS)"
                    value={stats.new7d > 0 ? stats.new7d.toLocaleString() : 'N/A'}
                    trendDirection={stats.new7d > 0 ? 'up' : 'neutral'}
                    variant={variant}
                />
            </div>
        </div>
    );
}
