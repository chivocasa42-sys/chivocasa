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

    return (
        <Link
            href={`/${slug}${filterSegment}`}
            className="dept-card"
        >
            {/* Badge - Top Right */}
            <div className="dept-card__badge">
                {totalCount}
            </div>

            {/* Header Section */}
            <div className="dept-card__header">
                <span className="dept-card__label">PRECIO MEDIANO</span>
                <span className="dept-card__price">{formatPrice(medianPrice)}</span>
                <h3 className="dept-card__name">{departamento}</h3>
            </div>

            {/* Divider */}
            <div className="dept-card__divider" />

            {/* Oferta Section */}
            <div className="dept-card__oferta">
                <span className="dept-card__oferta-label">Oferta</span>

                <div className="dept-card__pills-row">
                    {/* Venta Pill */}
                    <div className="dept-card__pill dept-card__pill--venta">
                        <span className="dept-card__pill-label dept-card__pill-label--venta">VENTA</span>
                        <span className="dept-card__pill-value">{saleCount ?? 0}</span>
                    </div>

                    {/* Vertical Divider */}
                    <div className="dept-card__pill-divider" />

                    {/* Renta Pill */}
                    <div className="dept-card__pill dept-card__pill--renta">
                        <span className="dept-card__pill-label dept-card__pill-label--renta">RENTA</span>
                        <span className="dept-card__pill-value">{rentCount ?? 0}</span>
                    </div>
                </div>

                {/* Rango Pill */}
                <div className="dept-card__rango">
                    <span className="dept-card__rango-label">RANGO</span>
                    <span className="dept-card__rango-value">
                        {formatPriceCompact(priceRangeMin)}→{formatPriceCompact(priceRangeMax)}
                    </span>
                </div>
            </div>
        </Link>
    );
}
