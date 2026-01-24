'use client';

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
}

function formatPrice(price: number): string {
    if (!price || price === 0) return 'N/A';
    return '$' + Math.round(price).toLocaleString('en-US');
}

export default function KPIStrip({ stats }: KPIStripProps) {
    return (
        <div className="mb-8">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-5">
                <KPICard
                    label="PRECIO TÍPICO VENTA"
                    value={formatPrice(stats.medianSale)}
                    trend={stats.saleTrend}
                    trendDirection={stats.saleTrend && stats.saleTrend > 0 ? 'up' : stats.saleTrend && stats.saleTrend < 0 ? 'down' : 'neutral'}
                    subtitle="Mediana nacional"
                />

                <KPICard
                    label="RENTA TÍPICA MENSUAL"
                    value={`${formatPrice(stats.medianRent)}/mes`}
                    trend={stats.rentTrend}
                    trendDirection={stats.rentTrend && stats.rentTrend > 0 ? 'up' : stats.rentTrend && stats.rentTrend < 0 ? 'down' : 'neutral'}
                    subtitle="Mediana nacional"
                />

                <KPICard
                    label="ACTIVOS HOY"
                    value={stats.totalActive.toLocaleString()}
                    subtitle="Propiedades activas"
                />

                <KPICard
                    label="NUEVOS (7 DÍAS)"
                    value={stats.new7d > 0 ? `+${stats.new7d}` : 'N/A'}
                    trendDirection={stats.new7d > 0 ? 'up' : 'neutral'}
                    subtitle="Últimos 7 días"
                />
            </div>
        </div>
    );
}
