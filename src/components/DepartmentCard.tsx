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
    activeFilter?: 'sale' | 'rent';
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

function getFilterSegment(filter?: 'sale' | 'rent'): string {
    if (filter === 'sale') return '/venta';
    if (filter === 'rent') return '/renta';
    return '';
}

export default function DepartmentCard({
    departamento, totalCount, saleCount, rentCount,
    medianPrice, priceRangeMin, priceRangeMax, slug, activeFilter
}: DepartmentCardProps) {
    const filterSegment = getFilterSegment(activeFilter);

    // Determine which pill to show and its count
    const showVenta = activeFilter === 'sale' || !activeFilter;
    const showRenta = activeFilter === 'rent';
    const pillCount = activeFilter === 'rent' ? (rentCount ?? 0) : (saleCount ?? 0);
    const pillLabel = activeFilter === 'rent' ? 'RENTA' : 'VENTA';
    const pillClass = activeFilter === 'rent' ? 'dept-card__pill--renta' : 'dept-card__pill--venta';
    const pillLabelClass = activeFilter === 'rent' ? 'dept-card__pill-label--renta' : 'dept-card__pill-label--venta';

    return (
        <Link
            href={`/${slug}${filterSegment}`}
            className="dept-card"
        >
            {/* Top-Right Badge: VENTA/RENTA Pill */}
            <div className="dept-card__badge-pill">
                <div className={`dept-card__pill ${pillClass}`}>
                    <span className={`dept-card__pill-label ${pillLabelClass}`}>{pillLabel}</span>
                    <span className="dept-card__pill-value">{pillCount}</span>
                </div>
            </div>

            {/* Header Section */}
            <div className="dept-card__header">
                <span className="dept-card__label">PRECIO MEDIANO</span>
                <span className="dept-card__price">{formatPrice(medianPrice)}</span>
                <h3 className="dept-card__name">{departamento}</h3>
            </div>

            {/* Divider */}
            <div className="dept-card__divider" />

            {/* Rango de precios Section */}
            <div className="dept-card__oferta">
                <span className="dept-card__oferta-label">Rango de precios</span>

                {/* Simple Price Range Pill */}
                <div className="dept-card__price-range">
                    {formatPriceCompact(priceRangeMin)} → {formatPriceCompact(priceRangeMax)}
                </div>
            </div>
        </Link>
    );
}
