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
                    <div className="card-float p-6 relative overflow-hidden flex flex-col h-full">
                        {/* Upper Header */}
                        <div className="flex justify-between items-start mb-4">
                            <span className="kpi-label font-bold text-[10px] tracking-widest text-slate-400">MEJOR RELACIÓN PRECIO-VALOR</span>
                            <span className="bg-emerald-500 text-white text-[10px] font-black px-2.5 py-1 rounded-lg uppercase tracking-wider shadow-sm">
                                VENTA
                            </span>
                        </div>

                        {/* Property Title */}
                        <div className="mb-4 flex-grow">
                            <h3 className="font-bold text-slate-900 text-lg leading-snug line-clamp-2 min-h-[3.5rem]">
                                {saleListing.title}
                            </h3>
                        </div>

                        {/* Price (Standardized with Hero Gradient) */}
                        <div className="mb-4">
                            <div className="text-3xl font-black hero-title-accent inline-block">
                                {formatPrice(saleListing.price)}
                            </div>
                        </div>

                        {/* Specs (Standardized Pills) */}
                        <div className="flex flex-wrap gap-2 mb-6">
                            {saleListing.mt2 > 0 && (
                                <span className="pill-range border border-slate-100 bg-slate-50 text-[11px] font-bold" title="Metros cuadrados">
                                    📐 {Math.round(saleListing.mt2)} m²
                                </span>
                            )}
                            {saleListing.bedrooms > 0 && (
                                <span className="pill-range border border-slate-100 bg-slate-50 text-[11px] font-bold" title="Habitaciones">
                                    🛏️ {Math.round(saleListing.bedrooms)}
                                </span>
                            )}
                            {saleListing.bathrooms > 0 && (
                                <span className="pill-range border border-slate-100 bg-slate-50 text-[11px] font-bold" title="Baños">
                                    🚿 {Math.round(saleListing.bathrooms)}
                                </span>
                            )}
                            {saleListing.price_per_m2 > 0 && (
                                <span className="pill-range border border-slate-100 bg-slate-50 text-[11px] font-bold" title="Precio por metro cuadrado">
                                    {formatPriceCompact(saleListing.price_per_m2)}/m²
                                </span>
                            )}
                        </div>

                        {/* Score (Standardized Progress Bar) */}
                        <div className="mt-auto border-t border-slate-50 pt-4">
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Score de oportunidad</span>
                                <span className="text-sm font-black text-[var(--primary)]">
                                    {saleListing.score.toFixed(2)}
                                </span>
                            </div>
                            <div className="h-2 bg-slate-100 rounded-full overflow-hidden mb-6">
                                <div
                                    className="h-full bg-gradient-to-r from-[var(--primary)] to-blue-400 rounded-full"
                                    style={{ width: `${Math.min(saleListing.score * 50, 100)}%` }}
                                />
                            </div>

                            {/* CTA */}
                            <button
                                onClick={() => onViewListing(saleListing)}
                                className="w-full btn-primary font-bold text-sm py-3 rounded-xl transition-all hover:scale-[1.02] active:scale-[0.98]"
                            >
                                Ver detalle →
                            </button>
                        </div>
                    </div>
                )}

                {/* Mejor Alquiler */}
                {rentListing && (
                    <div className="card-float p-6 relative overflow-hidden flex flex-col h-full">
                        {/* Upper Header */}
                        <div className="flex justify-between items-start mb-4">
                            <span className="kpi-label font-bold text-[10px] tracking-widest text-slate-400">MEJOR RELACIÓN PRECIO-VALOR</span>
                            <span className="bg-blue-600 text-white text-[10px] font-black px-2.5 py-1 rounded-lg uppercase tracking-wider shadow-sm">
                                RENTA
                            </span>
                        </div>

                        {/* Property Title */}
                        <div className="mb-4 flex-grow">
                            <h3 className="font-bold text-slate-900 text-lg leading-snug line-clamp-2 min-h-[3.5rem]">
                                {rentListing.title}
                            </h3>
                        </div>

                        {/* Price (Standardized with Hero Gradient) */}
                        <div className="mb-4">
                            <div className="text-3xl font-black hero-title-accent inline-block">
                                {formatPrice(rentListing.price)}
                            </div>
                            <span className="text-sm font-bold text-slate-400 ml-2">/mes</span>
                        </div>

                        {/* Specs (Standardized Pills) */}
                        <div className="flex flex-wrap gap-2 mb-6">
                            {rentListing.mt2 > 0 && (
                                <span className="pill-range border border-slate-100 bg-slate-50 text-[11px] font-bold" title="Metros cuadrados">
                                    📐 {Math.round(rentListing.mt2)} m²
                                </span>
                            )}
                            {rentListing.bedrooms > 0 && (
                                <span className="pill-range border border-slate-100 bg-slate-50 text-[11px] font-bold" title="Habitaciones">
                                    🛏️ {Math.round(rentListing.bedrooms)}
                                </span>
                            )}
                            {rentListing.bathrooms > 0 && (
                                <span className="pill-range border border-slate-100 bg-slate-50 text-[11px] font-bold" title="Baños">
                                    🚿 {Math.round(rentListing.bathrooms)}
                                </span>
                            )}
                            {rentListing.price_per_m2 > 0 && (
                                <span className="pill-range border border-slate-100 bg-slate-50 text-[11px] font-bold" title="Precio por metro cuadrado">
                                    {formatPriceCompact(rentListing.price_per_m2)}/m²
                                </span>
                            )}
                        </div>

                        {/* Score (Standardized Progress Bar) */}
                        <div className="mt-auto border-t border-slate-50 pt-4">
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Score de oportunidad</span>
                                <span className="text-sm font-black text-[var(--primary)]">
                                    {rentListing.score.toFixed(2)}
                                </span>
                            </div>
                            <div className="h-2 bg-slate-100 rounded-full overflow-hidden mb-6">
                                <div
                                    className="h-full bg-gradient-to-r from-[var(--primary)] to-blue-400 rounded-full"
                                    style={{ width: `${Math.min(rentListing.score * 50, 100)}%` }}
                                />
                            </div>

                            {/* CTA */}
                            <button
                                onClick={() => onViewListing(rentListing)}
                                className="w-full btn-primary font-bold text-sm py-3 rounded-xl transition-all hover:scale-[1.02] active:scale-[0.98]"
                            >
                                Ver detalle →
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
