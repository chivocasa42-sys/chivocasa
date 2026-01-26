'use client';

interface FeatureCardsProps {
    totalListings?: number;
    avgPrice?: number;
    departments?: number;
}

export default function FeatureCards({
    totalListings = 0,
    avgPrice = 0,
    departments = 14
}: FeatureCardsProps) {
    // Format currency
    const formatPrice = (price: number) => {
        if (price >= 1000) {
            return `$${(price / 1000).toFixed(0)}K`;
        }
        return `$${price.toLocaleString()}`;
    };

    return (
        <div className="feature-cards-container">
            {/* Card 1: Estadísticas */}
            <div className="feature-card">
                <span className="feature-card-label">Propiedades activas</span>
                <div className="feature-card-value">
                    {totalListings.toLocaleString()}
                </div>
                <div className="feature-card-subtitle">
                    Próxima actualización: Hoy
                </div>
                <div className="feature-chart">
                    <svg viewBox="0 0 200 60" className="w-full h-full" preserveAspectRatio="none">
                        <path
                            d="M0,45 Q30,40 50,35 T100,30 T150,25 T200,20"
                            fill="none"
                            stroke="var(--primary)"
                            strokeWidth="2"
                            opacity="0.5"
                        />
                        <path
                            d="M0,50 Q30,45 50,42 T100,38 T150,32 T200,28"
                            fill="none"
                            stroke="var(--text-muted)"
                            strokeWidth="1"
                            strokeDasharray="4,4"
                            opacity="0.3"
                        />
                    </svg>
                </div>
            </div>

            {/* Card 2: Conecta fuentes */}
            <div className="feature-card">
                <div className="feature-card-title">Explora departamentos</div>
                <div className="feature-card-icons">
                    <span className="feature-icon" title="San Salvador">🏙️</span>
                    <span className="feature-icon" title="La Libertad">🏖️</span>
                    <span className="feature-icon" title="Santa Ana">🌄</span>
                    <span className="feature-icon" title="San Miguel">🏔️</span>
                </div>
                <div className="feature-card-icons" style={{ marginTop: '0.75rem' }}>
                    <span className="feature-icon" title="Sonsonate">🌊</span>
                    <span className="feature-icon" title="Usulután">🌿</span>
                </div>
                <div style={{
                    marginTop: '1.5rem',
                    display: 'flex',
                    justifyContent: 'center'
                }}>
                    <a
                        href="#departamentos"
                        className="btn-primary"
                        style={{
                            borderRadius: '999px',
                            fontSize: '0.875rem',
                            padding: '0.625rem 1.25rem'
                        }}
                    >
                        Ver {departments} departamentos
                    </a>
                </div>
            </div>

            {/* Card 3: Insights */}
            <div className="feature-card">
                <div style={{
                    width: '28px',
                    height: '28px',
                    background: 'var(--primary)',
                    borderRadius: '8px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: 'white',
                    fontSize: '0.875rem',
                    marginBottom: '1rem'
                }}>
                    💡
                </div>

                <div className="chat-bubbles">
                    <div className="chat-bubble">
                        ¿Cuáles son las zonas más económicas?
                    </div>
                    <div className="chat-bubble right">
                        ¿Dónde hay más actividad de mercado?
                    </div>
                    <div className="chat-bubble">
                        ¿Cuál es el precio promedio en venta?
                    </div>
                </div>

                <div className="feature-cta">
                    <span>Descubre insights del mercado</span>
                    <span className="feature-arrow">→</span>
                </div>
            </div>
        </div>
    );
}
