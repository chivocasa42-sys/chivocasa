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

export default function DepartmentCard({
    departamento, totalCount, saleCount, rentCount,
    medianPrice, priceRangeMin, priceRangeMax, slug
}: DepartmentCardProps) {
    return (
        <Link
            href={`/${slug}`}
            className="card-float card-float-interactive flex flex-col"
        >
            {/* Header */}
            <div className="p-5 pb-3">
                <div className="flex justify-between items-start mb-3">
                    <h3 className="font-semibold text-base text-[var(--text-primary)]">
                        {departamento}
                    </h3>
                    <span className="badge-count">
                        {totalCount}
                    </span>
                </div>

                {/* Iconos con tooltips */}
                <div className="flex items-center gap-4 text-sm text-[var(--text-secondary)]">
                    {saleCount !== undefined && saleCount > 0 && (
                        <span
                            className="flex items-center gap-1.5"
                            title="Propiedades en venta"
                        >
                            <span>🏠</span>
                            <span className="font-medium">{saleCount}</span>
                        </span>
                    )}
                    {rentCount !== undefined && rentCount > 0 && (
                        <span
                            className="flex items-center gap-1.5"
                            title="Propiedades en alquiler"
                        >
                            <span>🔑</span>
                            <span className="font-medium">{rentCount}</span>
                        </span>
                    )}
                </div>
            </div>

            {/* Precio típico - centrado y prominente */}
            <div className="px-5 py-5 border-t border-slate-100 text-center flex-1">
                <div className="kpi-label mb-2">
                    PRECIO TÍPICO
                </div>
                <div className="kpi-value text-[var(--primary)]">
                    {formatPrice(medianPrice)}
                </div>
            </div>

            {/* Rango típico */}
            <div className="px-5 pb-4 text-center">
                <span className="pill-range">
                    {formatPriceCompact(priceRangeMin)} → {formatPriceCompact(priceRangeMax)}
                </span>
            </div>

            {/* CTA */}
            <div className="px-5 py-3 border-t border-slate-100 bg-[var(--bg-subtle)] rounded-b-2xl">
                <div className="text-sm text-[var(--primary)] font-medium flex items-center justify-end gap-1">
                    Ver propiedades
                    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 16 16">
                        <path fillRule="evenodd" d="M4.646 1.646a.5.5 0 0 1 .708 0l6 6a.5.5 0 0 1 0 .708l-6 6a.5.5 0 0 1-.708-.708L10.293 8 4.646 2.354a.5.5 0 0 1 0-.708z" />
                    </svg>
                </div>
            </div>
        </Link>
    );
}
