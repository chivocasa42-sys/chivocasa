'use client';

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
    first_image?: string | null;
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

    const renderOpportunityCard = (listing: TopScoredListing, type: 'sale' | 'rent') => {
        const isRent = type === 'rent';
        const badgeClass = isRent ? 'bg-blue-700' : 'bg-emerald-600';
        const badgeText = isRent ? 'RENTA' : 'VENTA';

        return (
            <div
                className="card-float overflow-hidden cursor-pointer hover:shadow-xl transition-all duration-200 hover:-translate-y-1"
                onClick={() => onViewListing(listing)}
            >
                {/* Image Section */}
                <div className="relative h-48 bg-gradient-to-br from-slate-100 to-slate-200 overflow-hidden">
                    {listing.first_image ? (
                        <img
                            src={listing.first_image}
                            alt="Propiedad"
                            className="w-full h-full object-cover"
                        />
                    ) : (
                        <div className="w-full h-full flex items-center justify-center text-slate-400">
                            <svg className="w-16 h-16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
                            </svg>
                        </div>
                    )}
                    {/* Badge Overlay */}
                    <div className="absolute top-3 right-3">
                        <span className={`${badgeClass} text-white text-[10px] font-black px-2.5 py-1 rounded-lg uppercase tracking-wider shadow-lg`}>
                            {badgeText}
                        </span>
                    </div>
                    {/* Label Overlay */}
                    <div className="absolute top-3 left-3">
                        <span className="bg-white/90 backdrop-blur-sm text-slate-700 text-[10px] font-bold px-2.5 py-1 rounded-lg uppercase tracking-wider shadow-md">
                            Mejor Relación Precio-Valor
                        </span>
                    </div>
                </div>

                {/* Content Section */}
                <div className="p-6">
                    {/* Price - Topmost */}
                    <div className="mb-4">
                        <div className="text-3xl font-black hero-title-accent inline-block">
                            {formatPrice(listing.price)}
                        </div>
                        {isRent && <span className="text-sm font-bold text-slate-400 ml-2">/mes</span>}
                    </div>

                    {/* Specs Pills */}
                    <div className="flex flex-wrap gap-2 mb-4">
                        {listing.mt2 > 0 && (
                            <span className="pill-range border border-slate-100 bg-slate-50 text-[11px] font-bold">
                                📐 {Math.round(listing.mt2)} m²
                            </span>
                        )}
                        {listing.bedrooms > 0 && (
                            <span className="pill-range border border-slate-100 bg-slate-50 text-[11px] font-bold">
                                🛏️ {Math.round(listing.bedrooms)}
                            </span>
                        )}
                        {listing.bathrooms > 0 && (
                            <span className="pill-range border border-slate-100 bg-slate-50 text-[11px] font-bold">
                                🚿 {Math.round(listing.bathrooms)}
                            </span>
                        )}
                        {listing.price_per_m2 > 0 && (
                            <span className="pill-range border border-slate-100 bg-slate-50 text-[11px] font-bold">
                                {formatPriceCompact(listing.price_per_m2)}/m²
                            </span>
                        )}
                    </div>

                    {/* Score */}
                    <div className="border-t border-slate-50 pt-4">
                        <div className="flex items-center justify-between mb-2">
                            <span className="text-[10px] font-bold uppercase tracking-widest text-slate-600">Score de oportunidad</span>
                            <span className="text-sm font-black text-[var(--primary)]">
                                {listing.score.toFixed(2)}
                            </span>
                        </div>
                        <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                            <div
                                className="h-full bg-gradient-to-r from-[var(--primary)] to-blue-400 rounded-full transition-all duration-500"
                                style={{ width: `${Math.min(listing.score * 50, 100)}%` }}
                            />
                        </div>
                    </div>
                </div>
            </div>
        );
    };

    return (
        <div className="mb-8">
            <h2 className="text-lg font-semibold text-[var(--text-primary)] mb-4 flex items-center gap-2">
                <span className="text-xl">💎</span>
                Mejores Oportunidades
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                {saleListing && renderOpportunityCard(saleListing, 'sale')}
                {rentListing && renderOpportunityCard(rentListing, 'rent')}
            </div>
        </div>
    );
}
