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

const periodLabels: Record<PeriodType, string> = {
    '7d': '7 días',
    '30d': '30 días',
    '90d': '90 días'
};

const viewLabels: Record<ViewType, string> = {
    'all': 'Todos',
    'sale': 'Venta',
    'rent': 'Renta'
};

const orderLabels: Record<OrderType, string> = {
    'activity': 'Actividad',
    'price': 'Precio',
    'variation': 'Variación'
};

export default function HomeHeader({
    period, view, orderBy,
    onPeriodChange, onViewChange, onOrderChange
}: HomeHeaderProps) {
    return (
        <div className="mb-6">
            {/* Control Bar - Responsive Flex Layout */}
            <div className="flex flex-col md:flex-row md:items-end justify-between gap-6">
                {/* LEFT: Periodo */}
                <div className="control-group">
                    <label className="control-label">Periodo</label>
                    <div className="segmented-control">
                        {(['7d', '30d', '90d'] as PeriodType[]).map(p => (
                            <button
                                key={p}
                                onClick={() => onPeriodChange(p)}
                                className={`segmented-btn ${period === p ? 'active' : ''}`}
                            >
                                {periodLabels[p]}
                            </button>
                        ))}
                    </div>
                </div>

                {/* CENTER: Mercado */}
                <div className="control-group">
                    <label className="control-label">Mercado</label>
                    <div className="segmented-control">
                        {(['all', 'sale', 'rent'] as ViewType[]).map(v => (
                            <button
                                key={v}
                                onClick={() => onViewChange(v)}
                                className={`segmented-btn ${view === v ? 'active' : ''}`}
                            >
                                {viewLabels[v]}
                            </button>
                        ))}
                    </div>
                </div>

                {/* RIGHT: Ordenar */}
                <div className="control-group">
                    <label className="control-label">Ordenar por</label>
                    <div className="dropdown-control">
                        <select
                            value={orderBy}
                            onChange={(e) => onOrderChange(e.target.value as OrderType)}
                            className="dropdown-select w-full md:w-auto"
                        >
                            <option value="activity">{orderLabels.activity}</option>
                            <option value="price">{orderLabels.price}</option>
                            <option value="variation">{orderLabels.variation}</option>
                        </select>
                        <svg
                            className="dropdown-icon"
                            width="12"
                            height="12"
                            viewBox="0 0 12 12"
                            fill="none"
                        >
                            <path
                                d="M3 4.5L6 7.5L9 4.5"
                                stroke="currentColor"
                                strokeWidth="1.5"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                            />
                        </svg>
                    </div>
                </div>
            </div>

            {/* Status Line */}
            <div className="status-line mt-4">
                Mostrando: <span>{periodLabels[period]}</span> · <span>{viewLabels[view]}</span> · Orden: <span>{orderLabels[orderBy]}</span>
            </div>
        </div>
    );
}
