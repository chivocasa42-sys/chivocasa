'use client';

import Link from 'next/link';

interface DepartmentCardProps {
    departamento: string;
    totalCount: number;
    saleCount?: number;
    rentCount?: number;
    medianPrice: number;
    priceRangeMin: number;
    priceRangeMax: number;
    slug: string;
    activeFilter?: 'sale' | 'rent'; // Pass current filter to persist in navigation
}

function formatPrice(price: number): string {
    if (!price || price === 0) return 'N/A';
    return '$' + Math.round(price).toLocaleString('en-US');
}

function formatPriceCompact(price: number): string {
    if (!price || price === 0) return 'N/A';
    if (price >= 1000000) return '$' + (price / 1000000).toFixed(1) + 'M';
    if (price >= 1000) return '$' + Math.round(price / 1000) + 'K';
    return '$' + Math.round(price).toLocaleString();
}

// Map filter to URL segment
function getFilterSegment(filter?: 'sale' | 'rent'): string {
    if (filter === 'sale') return '/venta';
    if (filter === 'rent') return '/renta';
    return ''; // Default: no segment (shows all)
}

export default function DepartmentCard({
    departamento, totalCount, saleCount, rentCount,
    medianPrice, priceRangeMin, priceRangeMax, slug, activeFilter
}: DepartmentCardProps) {
    const filterSegment = getFilterSegment(activeFilter);

    return (
        <Link
            href={`/${slug}${filterSegment}`}
            className="card-float card-float-interactive flex flex-col pt-4 sm:pt-6 pb-3 sm:pb-4 relative min-h-[140px] sm:min-h-[160px]"
        >
            {/* Total Count Bubble - Top Right Absolute */}
            <div className="absolute top-3 sm:top-4 right-3 sm:right-4">
                <span className="badge-count">
                    {totalCount}
                </span>
            </div>

            {/* Precio Típico Section */}
            <div className="px-4 sm:px-5 mt-3 sm:mt-4 mb-1 sm:mb-2 text-center">
                <div className="kpi-label mb-0.5 sm:mb-1 text-[10px] sm:text-xs uppercase tracking-wider text-[var(--text-muted)]">
                    PRECIO MEDIO
                </div>
                <div className="text-2xl sm:text-3xl font-bold text-[var(--text-primary)]">
                    {formatPrice(medianPrice)}
                </div>
            </div>

            {/* Department Name */}
            <div className="px-4 sm:px-5 mb-3 sm:mb-4 text-center">
                <h3 className="font-semibold text-base sm:text-lg text-[var(--text-primary)]">
                    {departamento}
                </h3>

                {/* Iconos */}
                <div className="flex justify-center items-center gap-3 text-sm text-[var(--text-secondary)] mt-1">
                    {saleCount !== undefined && saleCount > 0 && (
                        <span className="flex items-center gap-1.5" title="Propiedades en venta">
                            <span>🏠</span>
                            <span className="font-medium">{saleCount}</span>
                        </span>
                    )}
                    {rentCount !== undefined && rentCount > 0 && (
                        <span className="flex items-center gap-1.5" title="Propiedades en renta">
                            <span>🔑</span>
                            <span className="font-medium">{rentCount}</span>
                        </span>
                    )}
                </div>
            </div>

            {/* Rango típico */}
            <div className="px-5 text-center mt-auto">
                <span className="pill-range text-xs bg-slate-100 text-[var(--text-secondary)] py-1 px-3 rounded-full">
                    {formatPriceCompact(priceRangeMin)} → {formatPriceCompact(priceRangeMax)}
                </span>
            </div>
        </Link>
    );
}
