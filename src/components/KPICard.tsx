'use client';

interface KPICardProps {
    label: string;
    value: string;
    trend?: number;
    trendDirection?: 'up' | 'down' | 'neutral';
    subtitle?: string;
    icon?: React.ReactNode;
}

export default function KPICard({ label, value, trend, trendDirection = 'neutral', subtitle }: KPICardProps) {
    const getTrendColor = () => {
        if (trendDirection === 'up') return 'trend-up';
        if (trendDirection === 'down') return 'trend-down';
        return 'trend-neutral';
    };

    const getTrendIcon = () => {
        if (trendDirection === 'up') return '▲';
        if (trendDirection === 'down') return '▼';
        return '—';
    };

    return (
        <div className="card-float card-kpi p-5 text-center">
            {/* Label */}
            <div className="kpi-label mb-3">
                {label}
            </div>

            {/* Value */}
            <div className="kpi-value text-[var(--primary)]">
                {value}
            </div>

            {/* Trend */}
            {trend !== undefined && (
                <div className={`mt-2 text-sm font-medium ${getTrendColor()}`}>
                    <span title={trendDirection === 'up' ? 'Subió vs período anterior' : trendDirection === 'down' ? 'Bajó vs período anterior' : 'Sin cambio'}>
                        {getTrendIcon()} {Math.abs(trend).toFixed(1)}%
                    </span>
                </div>
            )}

            {/* Subtitle */}
            {subtitle && (
                <div className="mt-1 text-xs text-[var(--text-muted)]">
                    {subtitle}
                </div>
            )}
        </div>
    );
}
