'use client';

import Link from 'next/link';

interface TopScoredListing {
    external_id: number;
    title: string;
    price: number;
    mt2: number;
    bedrooms: number;
    bathrooms: number;
    price_per_m2: number;
    score: number;
    url: string;
}

interface BestOpportunitySectionProps {
    saleListing: TopScoredListing | null;
    rentListing: TopScoredListing | null;
    onViewListing: (listing: TopScoredListing) => void;
}

function formatPrice(price: number): string {
    if (!price || price === 0) return 'N/A';
    return '$' + Math.round(price).toLocaleString('en-US');
}

function formatPriceCompact(price: number): string {
    if (!price || price === 0) return 'N/A';
    if (price >= 1000) return '$' + Math.round(price / 1000) + 'K';
    return '$' + Math.round(price).toLocaleString();
}

export default function BestOpportunitySection({
    saleListing, rentListing, onViewListing
}: BestOpportunitySectionProps) {
    if (!saleListing && !rentListing) return null;

    return (
        <div className="mb-8">
            <h2 className="text-lg font-semibold text-[var(--text-primary)] mb-4 flex items-center gap-2">
                <span className="text-xl">💎</span>
                Mejores Oportunidades
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                {/* Mejor Venta */}
                {saleListing && (
                    <div className="card-float p-5 relative overflow-hidden">
                        {/* Badge */}
                        <div className="absolute top-4 right-4">
                            <span className="bg-[var(--success)] text-white text-xs font-bold px-3 py-1 rounded-full">
                                MEJOR VENTA
                            </span>
                        </div>

                        {/* Content */}
                        <div className="mb-4">
                            <span className="kpi-label">Mejor relación precio-valor</span>
                            <h3 className="font-semibold text-[var(--text-primary)] mt-2 pr-24 line-clamp-2">
                                {saleListing.title}
                            </h3>
                        </div>

                        {/* Price */}
                        <div className="text-3xl font-bold text-[var(--success)] mb-3">
                            {formatPrice(saleListing.price)}
                        </div>

                        {/* Specs */}
                        <div className="flex flex-wrap gap-3 mb-4">
                            {saleListing.mt2 > 0 && (
                                <span className="pill-range" title="Metros cuadrados">
                                    📐 {Math.round(saleListing.mt2)} m²
                                </span>
                            )}
                            {saleListing.bedrooms > 0 && (
                                <span className="pill-range" title="Habitaciones">
                                    🛏️ {Math.round(saleListing.bedrooms)}
                                </span>
                            )}
                            {saleListing.bathrooms > 0 && (
                                <span className="pill-range" title="Baños">
                                    🚿 {Math.round(saleListing.bathrooms)}
                                </span>
                            )}
                            {saleListing.price_per_m2 > 0 && (
                                <span className="pill-range" title="Precio por metro cuadrado">
                                    {formatPriceCompact(saleListing.price_per_m2)}/m²
                                </span>
                            )}
                        </div>

                        {/* Score indicator */}
                        <div className="flex items-center gap-2 mb-4">
                            <span className="text-xs text-[var(--text-muted)]">Score de oportunidad:</span>
                            <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
                                <div
                                    className="h-full bg-gradient-to-r from-[var(--success)] to-emerald-400 rounded-full"
                                    style={{ width: `${Math.min(saleListing.score * 50, 100)}%` }}
                                />
                            </div>
                            <span className="text-sm font-semibold text-[var(--success)]">
                                {saleListing.score.toFixed(2)}
                            </span>
                        </div>

                        {/* CTA */}
                        <button
                            onClick={() => onViewListing(saleListing)}
                            className="w-full btn-primary text-center"
                        >
                            Ver detalle →
                        </button>
                    </div>
                )}

                {/* Mejor Alquiler */}
                {rentListing && (
                    <div className="card-float p-5 relative overflow-hidden">
                        {/* Badge */}
                        <div className="absolute top-4 right-4">
                            <span className="bg-[var(--primary)] text-white text-xs font-bold px-3 py-1 rounded-full">
                                MEJOR RENTA
                            </span>
                        </div>

                        {/* Content */}
                        <div className="mb-4">
                            <span className="kpi-label">Mejor relación precio-valor</span>
                            <h3 className="font-semibold text-[var(--text-primary)] mt-2 pr-24 line-clamp-2">
                                {rentListing.title}
                            </h3>
                        </div>

                        {/* Price */}
                        <div className="text-3xl font-bold text-[var(--primary)] mb-3">
                            {formatPrice(rentListing.price)}
                            <span className="text-base font-normal text-[var(--text-muted)]">/mes</span>
                        </div>

                        {/* Specs */}
                        <div className="flex flex-wrap gap-3 mb-4">
                            {rentListing.mt2 > 0 && (
                                <span className="pill-range" title="Metros cuadrados">
                                    📐 {Math.round(rentListing.mt2)} m²
                                </span>
                            )}
                            {rentListing.bedrooms > 0 && (
                                <span className="pill-range" title="Habitaciones">
                                    🛏️ {Math.round(rentListing.bedrooms)}
                                </span>
                            )}
                            {rentListing.bathrooms > 0 && (
                                <span className="pill-range" title="Baños">
                                    🚿 {Math.round(rentListing.bathrooms)}
                                </span>
                            )}
                            {rentListing.price_per_m2 > 0 && (
                                <span className="pill-range" title="Precio por metro cuadrado">
                                    {formatPriceCompact(rentListing.price_per_m2)}/m²
                                </span>
                            )}
                        </div>

                        {/* Score indicator */}
                        <div className="flex items-center gap-2 mb-4">
                            <span className="text-xs text-[var(--text-muted)]">Score de oportunidad:</span>
                            <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
                                <div
                                    className="h-full bg-gradient-to-r from-[var(--primary)] to-blue-400 rounded-full"
                                    style={{ width: `${Math.min(rentListing.score * 50, 100)}%` }}
                                />
                            </div>
                            <span className="text-sm font-semibold text-[var(--primary)]">
                                {rentListing.score.toFixed(2)}
                            </span>
                        </div>

                        {/* CTA */}
                        <button
                            onClick={() => onViewListing(rentListing)}
                            className="w-full btn-primary text-center"
                        >
                            Ver detalle →
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
}
