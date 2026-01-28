'use client';

type ViewType = 'all' | 'sale' | 'rent';

interface HomeHeaderProps {
    view: ViewType;
    onViewChange: (view: ViewType) => void;
}

const viewLabels: Record<ViewType, string> = {
    'all': 'Todos',
    'sale': 'Venta',
    'rent': 'Renta'
};

export default function HomeHeader({
    view,
    onViewChange
}: HomeHeaderProps) {
    return (
        <div className="mb-6">
            {/* Control Bar - Centered */}
            <div className="flex justify-center">
                {/* Mercado Filter */}
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
            </div>
        </div>
    );
}
