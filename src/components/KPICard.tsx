interface KPICardProps {
    label: string;
    value: string;
    trend?: number;
    trendDirection?: 'up' | 'down' | 'neutral';
    subtitle?: string;
    variant?: 'default' | 'home';
}

export default function KPICard({
    label,
    value,
    trend,
    trendDirection = 'neutral',
    subtitle,
    variant = 'default',
}: KPICardProps) {
    const getTrendColor = () => {
        if (trendDirection === 'up') return 'trend-up';
        if (trendDirection === 'down') return 'trend-down';
        return 'trend-neutral';
    };

    const getTrendPrefix = () => {
        if (trendDirection === 'up') return '+';
        if (trendDirection === 'down') return '-';
        return '=';
    };

    const trendTitle =
        trendDirection === 'up'
            ? 'Subio vs periodo anterior'
            : trendDirection === 'down'
                ? 'Bajo vs periodo anterior'
                : 'Sin cambio';

    if (variant === 'home') {
        return (
            <div className="card-float card-kpi home-kpi-card">
                <div className="home-kpi-label">{label}</div>

                <div className="home-kpi-value">
                    {value}
                </div>

                {trend !== undefined ? (
                    <div className={`home-kpi-trend ${getTrendColor()}`}>
                        <span title={trendTitle}>
                            {getTrendPrefix()} {Math.abs(trend).toFixed(1)}%
                        </span>
                    </div>
                ) : subtitle ? (
                    <div className="home-kpi-subtitle">
                        {subtitle}
                    </div>
                ) : null}
            </div>
        );
    }

    return (
        <div className="card-float card-kpi p-5 text-center">
            <div className="kpi-value text-[var(--primary)]">
                {value}
            </div>

            <div className="kpi-label mb-3">
                {label}
            </div>

            {trend !== undefined && (
                <div className={`mt-2 text-sm font-medium ${getTrendColor()}`}>
                    <span title={trendTitle}>
                        {getTrendPrefix()} {Math.abs(trend).toFixed(1)}%
                    </span>
                </div>
            )}

            {subtitle && (
                <div className="mt-1 text-xs text-[var(--text-muted)]">
                    {subtitle}
                </div>
            )}
        </div>
    );
}
