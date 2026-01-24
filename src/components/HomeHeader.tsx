'use client';

type PeriodType = '7d' | '30d' | '90d';
type ViewType = 'all' | 'sale' | 'rent';
type OrderType = 'activity' | 'price' | 'variation';

interface HomeHeaderProps {
    period: PeriodType;
    view: ViewType;
    orderBy: OrderType;
    onPeriodChange: (period: PeriodType) => void;
    onViewChange: (view: ViewType) => void;
    onOrderChange: (order: OrderType) => void;
}

export default function HomeHeader({
    period, view, orderBy,
    onPeriodChange, onViewChange, onOrderChange
}: HomeHeaderProps) {
    return (
        <div className="mb-8">
            {/* Título */}
            <div className="mb-6">
                <h1 className="text-2xl font-bold text-[var(--text-primary)] tracking-wide">
                    ÍNDICE INMOBILIARIO · EL SALVADOR
                </h1>
                <p className="text-[var(--text-secondary)] mt-1">
                    Datos agregados del mercado inmobiliario salvadoreño
                </p>
            </div>

            {/* Controles */}
            <div className="flex flex-wrap items-center gap-4">
                {/* Período */}
                <div className="pill-group">
                    {(['7d', '30d', '90d'] as PeriodType[]).map(p => (
                        <button
                            key={p}
                            onClick={() => onPeriodChange(p)}
                            className={`pill-btn ${period === p ? 'active' : ''}`}
                        >
                            {p.toUpperCase()}
                        </button>
                    ))}
                </div>

                {/* Vista */}
                <div className="pill-group">
                    <button
                        onClick={() => onViewChange('all')}
                        className={`pill-btn ${view === 'all' ? 'active' : ''}`}
                    >
                        Todo
                    </button>
                    <button
                        onClick={() => onViewChange('sale')}
                        className={`pill-btn ${view === 'sale' ? 'active' : ''}`}
                    >
                        Venta
                    </button>
                    <button
                        onClick={() => onViewChange('rent')}
                        className={`pill-btn ${view === 'rent' ? 'active' : ''}`}
                    >
                        Renta
                    </button>
                </div>

                {/* Ordenar */}
                <div className="flex items-center gap-2">
                    <span className="text-sm text-[var(--text-muted)]">Ordenar:</span>
                    <select
                        value={orderBy}
                        onChange={(e) => onOrderChange(e.target.value as OrderType)}
                        className="text-sm border border-slate-200 rounded-lg px-3 py-1.5 bg-white text-[var(--text-secondary)]"
                    >
                        <option value="activity">Actividad</option>
                        <option value="price">Precio</option>
                        <option value="variation">Variación</option>
                    </select>
                </div>
            </div>
        </div>
    );
}
