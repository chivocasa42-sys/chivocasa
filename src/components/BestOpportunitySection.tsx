'use client';

import { useMemo, useState } from 'react';

interface TopScoredListing {
    external_id: string | number;
    title: string;
    price: number;
    mt2: number;
    bedrooms: number;
    bathrooms: number;
    price_per_m2: number;
    score: number;
    url: string;
    first_image?: string | null;
}

interface BestOpportunitySectionProps {
    saleListing: TopScoredListing | null;
    rentListing: TopScoredListing | null;
    onViewListing: (listing: TopScoredListing) => void;
    departamentoName?: string;
}

function formatPrice(price: number): string {
    if (!price || price === 0) return 'N/A';
    return '$' + Math.round(price).toLocaleString('en-US');
}

export default function BestOpportunitySection({
    saleListing, rentListing, onViewListing, departamentoName
}: BestOpportunitySectionProps) {
    if (!saleListing && !rentListing) return null;

    const [isHowOpen, setIsHowOpen] = useState(false);

    const items = useMemo(() => {
        const next: Array<{ listing: TopScoredListing; type: 'sale' | 'rent' }> = [];
        if (saleListing) next.push({ listing: saleListing, type: 'sale' });
        if (rentListing) next.push({ listing: rentListing, type: 'rent' });
        return next;
    }, [saleListing, rentListing]);

    const getReason = (listing: TopScoredListing) => {
        if (listing.price_per_m2 > 0) return 'MEJOR PRECIO POR m²';
        if (listing.bathrooms > 0) return 'MÁS BAÑOS POR $';
        return 'MEJOR RELACIÓN PRECIO–VALOR';
    };

    return (
        <>
            {/* Main Section */}
            <div className="oportunidades-section">
                {/* Section Title */}
                <h2 className="text-2xl md:text-3xl font-black text-[var(--text-primary)] tracking-tight text-center mb-6">Oportunidades Destacadas</h2>

                {/* Card Container */}
                <div className="oportunidades-card">
                    {/* Header */}
                    <div className="oportunidades-header">
                        <div className="oportunidades-header-left">
                            <span className="oportunidades-star">★</span>
                            <span className="oportunidades-header-title">TOP PICKS DEL SISTEMA</span>
                        </div>
                        <p className="oportunidades-header-subtitle">
                            Seleccionadas por <strong>mejor relación</strong> precio-valor{departamentoName ? ` en ${departamentoName}.` : '.'}
                        </p>
                        <button
                            type="button"
                            onClick={() => setIsHowOpen(true)}
                            className="oportunidades-ver-todas"
                        >
                            Ver todas →
                        </button>
                    </div>

                    {/* Divider */}
                    <div className="oportunidades-divider"></div>

                    {/* Cards Grid */}
                    <div className="oportunidades-grid">
                        {items.map((item, idx) => {
                            const listing = item.listing;
                            const isRent = item.type === 'rent';
                            const reason = getReason(listing);
                            const hasImage = listing.first_image && listing.first_image.length > 0;

                            return (
                                <div
                                    key={`${item.type}-${listing.external_id}`}
                                    className={`oportunidad-card ${isRent ? 'oportunidad-card--rent' : 'oportunidad-card--sale'}`}
                                    onClick={() => onViewListing(listing)}
                                >
                                    {/* Property Image */}
                                    <div className="oportunidad-image-wrapper">
                                        {hasImage ? (
                                            <img
                                                src={listing.first_image!}
                                                alt={listing.title || 'Propiedad'}
                                                className="oportunidad-image"
                                                loading={idx === 0 ? 'eager' : 'lazy'}
                                                referrerPolicy="no-referrer"
                                            />
                                        ) : (
                                            <div className="oportunidad-image-placeholder">
                                                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1">
                                                    <path d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" strokeLinecap="round" strokeLinejoin="round" />
                                                </svg>
                                            </div>
                                        )}
                                        {/* Overlay badges */}
                                        <div className="oportunidad-image-overlay">
                                            <span className="oportunidad-rank-badge">#{idx + 1}</span>
                                            <span className={`oportunidad-type-badge ${isRent ? 'oportunidad-type-badge--rent' : 'oportunidad-type-badge--sale'}`}>
                                                {isRent ? 'RENTA' : 'VENTA'}
                                            </span>
                                        </div>
                                    </div>

                                    {/* Content Section */}
                                    <div className="oportunidad-content">
                                        {/* Price */}
                                        <div className="oportunidad-price-section">
                                            <span className="oportunidad-price">
                                                {formatPrice(listing.price)}
                                                {isRent && <span className="oportunidad-price-suffix">/mes</span>}
                                            </span>
                                        </div>

                                        {/* Reason Label */}
                                        <div className={`oportunidad-reason ${isRent ? 'oportunidad-reason--rent' : ''}`}>
                                            {reason}
                                        </div>

                                        {/* Datos Clave Divider */}
                                        <div className="datos-clave-label">
                                            <span className="datos-clave-line"></span>
                                            <span className="datos-clave-text">DATOS CLAVE</span>
                                            <span className="datos-clave-line"></span>
                                        </div>

                                        {/* Mini Cards */}
                                        <div className="datos-clave-grid">
                                            {/* ÁREA */}
                                            <div className="dato-card">
                                                <div className="dato-icon">
                                                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                                                        <path d="M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4z" strokeLinecap="round" strokeLinejoin="round" />
                                                        <path d="M14 14h6v6h-6" strokeLinecap="round" strokeLinejoin="round" strokeDasharray="2 2" />
                                                    </svg>
                                                </div>
                                                <div className="dato-value">{listing.mt2 > 0 ? Math.round(listing.mt2).toLocaleString() : '—'} m²</div>
                                                <div className="dato-label">ÁREA</div>
                                            </div>

                                            {/* AMBIENTES */}
                                            <div className="dato-card">
                                                <div className="dato-icons-row">
                                                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                                                        <path d="M3 12h18M3 12v6a2 2 0 002 2h14a2 2 0 002-2v-6M3 12V8a4 4 0 014-4h10a4 4 0 014 4v4" strokeLinecap="round" strokeLinejoin="round" />
                                                    </svg>
                                                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                                                        <path d="M4 12h16a2 2 0 012 2v2a2 2 0 01-2 2H4a2 2 0 01-2-2v-2a2 2 0 012-2zM6 12V8a2 2 0 012-2h2a2 2 0 012 2v4" strokeLinecap="round" strokeLinejoin="round" />
                                                    </svg>
                                                </div>
                                                <div className="dato-value">{listing.bedrooms > 0 ? Math.round(listing.bedrooms) : '—'} hab · {listing.bathrooms > 0 ? Math.round(listing.bathrooms) : '—'} baño{listing.bathrooms !== 1 ? 's' : ''}</div>
                                                <div className="dato-label">AMBIENTES</div>
                                            </div>

                                            {/* PUNTAJE */}
                                            <div className="dato-card">
                                                <div className="dato-icon">
                                                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                                                        <path d="M12 15l-3 3h6l-3-3zM8 9a4 4 0 118 0c0 2-2 3-2 5H10c0-2-2-3-2-5z" strokeLinecap="round" strokeLinejoin="round" />
                                                        <path d="M12 2v1M4.22 4.22l.7.7M2 12h1M4.22 19.78l.7-.7M20.78 4.22l-.7.7M22 12h-1M20.78 19.78l-.7-.7" strokeLinecap="round" />
                                                    </svg>
                                                </div>
                                                <div className="dato-value">
                                                    <span className="dato-score">{listing.score.toFixed(1)}</span>
                                                    <span className="dato-score-max">/ 10</span>
                                                </div>
                                                <div className="dato-label">PUNTAJE</div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            </div>

            {/* Modal */}
            {isHowOpen && (
                <div className="modal-backdrop" onClick={() => setIsHowOpen(false)}>
                    <div className="modal-content-premium" onClick={(e) => e.stopPropagation()}>
                        <button
                            type="button"
                            className="modal-close-btn"
                            onClick={() => setIsHowOpen(false)}
                            aria-label="Cerrar"
                        >
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                            </svg>
                        </button>
                        <div className="p-6 md:p-8">
                            <h3 className="text-lg font-semibold text-[var(--text-primary)] mb-2">¿Cómo se calcula?</h3>
                            <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
                                Seleccionamos oportunidades comparando precio, tamaño (m²) y características (habitaciones, baños),
                                buscando la mejor relación precio–valor dentro del departamento. El score se normaliza por tipo
                                (venta o renta) y se re-calcula periódicamente.
                            </p>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}
