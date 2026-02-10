'use client';

import { Listing, ListingSpecs, ListingLocation } from '@/types/listing';
import LazyImage from './LazyImage';

interface ListingCardProps {
    listing: Listing;
    onClick?: () => void;
    isFeatured?: boolean;
}

function formatPrice(price: number): string {
    if (!price) return 'N/A';
    return '$' + price.toLocaleString('en-US');
}

function getArea(specs: ListingSpecs | undefined | null): number {
    if (!specs) return 0;

    // Priority: area_m2 (normalized by scraper) > fallback fields
    // area_m2 can be stored as string or number
    if (specs.area_m2) {
        const numValue = parseFloat(String(specs.area_m2));
        if (numValue > 0) return numValue;
    }

    // Check various area field names
    const areaFields = [
        'Área construida (m²)',
        'area',
        'terreno',          // Land size from Realtor
        'Área del terreno',
        'm2',
        'metros',
        'habitaciones',     // Sometimes area is here
    ];

    for (const field of areaFields) {
        const value = specs[field];
        if (value) {
            const numValue = parseFloat(String(value).replace(/[^\d.]/g, ''));
            if (numValue > 0) return numValue;
        }
    }

    return 0;
}

function getImageUrl(images: string[] | null | undefined): string {
    if (!images || images.length === 0) {
        return '/placeholder.webp';
    }
    const firstImage = Array.isArray(images) ? images[0] : images;
    return firstImage || '/placeholder.webp';
}

// Get location-based tags from the listing
function getLocationTags(location: ListingLocation | undefined, tags?: string[] | null): string[] {
    // Tags to exclude from display (all listings are in El Salvador, so redundant)
    const excludedTags = ['el salvador', 'no identificado'];

    // Prefer the tags array if it exists
    if (tags && tags.length > 0) {
        return tags
            .filter(t => !excludedTags.includes(t.toLowerCase()))
            .slice(0, 3); // Max 3 location tags
    }

    // Fallback to building from location object
    const locationTags: string[] = [];
    if (location && typeof location === 'object') {
        if (location.municipio_detectado) locationTags.push(location.municipio_detectado);
        if (location.departamento) locationTags.push(location.departamento);
    } else if (typeof location === 'string') {
        locationTags.push(location);
    }

    return locationTags.slice(0, 3);
}

// Get human-readable "time since" text in Spanish
function getTimeSinceText(dateStr: string | undefined | null): string | null {
    if (!dateStr) return null;
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return null;

    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    if (diffMs < 0) return null;

    const days = Math.floor(diffMs / 86400000);

    if (days === 0) return 'Hoy';
    if (days === 1) return 'Hace 1 día';
    if (days < 7) return `Hace ${days} días`;
    if (days < 14) return 'Hace 1 semana';
    if (days < 30) return `Hace ${Math.floor(days / 7)} semanas`;
    if (days < 60) return 'Hace 1 mes';
    if (days < 365) return `Hace ${Math.floor(days / 30)} meses`;
    return `Hace más de 1 año`;
}

export default function ListingCard({ listing, onClick, isFeatured }: ListingCardProps) {
    const specs = listing.specs || {};
    const area = getArea(specs);
    const locationTags = getLocationTags(listing.location, listing.tags);
    const timeSinceText = getTimeSinceText(listing.published_date);

    return (
        <article
            className="group bg-white rounded-lg shadow-sm border border-slate-200 hover:shadow-xl transition-all cursor-pointer overflow-hidden focus-visible:outline-2 focus-visible:outline-[var(--primary)] focus-visible:outline-offset-2"
            onClick={onClick}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick?.(); } }}
            tabIndex={0}
            role="button"
            aria-label={listing.title || `Propiedad - ${formatPrice(listing.price)}`}
        >
            {/* Image Section - Larger aspect ratio */}
            <div className="relative aspect-[4/3] overflow-hidden">
                <LazyImage
                    src={getImageUrl(listing.images)}
                    alt={listing.title || 'Propiedad en venta o renta'}
                    className="w-full h-full group-hover:scale-105 transition-transform duration-500"
                    placeholderSrc="/placeholder.webp"
                />

                {isFeatured && (
                    <div className="absolute top-3 right-3">
                        <span className="bg-[var(--primary)] text-white text-[10px] font-black px-2.5 py-1 rounded shadow-sm uppercase tracking-wider">
                            DESTACADA
                        </span>
                    </div>
                )}

                {/* Top-left Label */}
                <div className="absolute top-3 left-3">
                    <span className="bg-white/95 backdrop-blur-sm text-slate-800 text-[11px] font-bold px-2.5 py-1 rounded shadow-sm uppercase tracking-wide flex items-center gap-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-red-500"></span>
                        {listing.listing_type === 'sale' ? 'En Venta' : 'En Renta'}
                    </span>
                </div>



                {/* Bottom-right Logo */}
                <div className="absolute bottom-2 right-2 bg-white/90 backdrop-blur-sm px-2 py-0.5 rounded text-[9px] font-black italic tracking-tight text-slate-800 shadow-sm">
                    SIVAR<span className="text-blue-600">CASAS</span>
                </div>
            </div>

            {/* Content Section */}
            <div className="p-4">
                {/* Price */}
                <div className="text-2xl font-black text-[#272727] tracking-tight mb-1">
                    {formatPrice(listing.price)}
                    {listing.listing_type === 'rent' && (
                        <span className="text-sm font-normal text-slate-500 ml-1">/mes</span>
                    )}
                </div>

                {/* Specs Inline Row */}
                <div className="flex items-center gap-1.5 text-[13px] text-slate-700 font-medium mb-1">
                    {specs.bedrooms !== undefined && (
                        <span><span className="font-bold">{specs.bedrooms}</span> hab</span>
                    )}
                    {(specs.bedrooms !== undefined && specs.bathrooms !== undefined) && <span className="text-slate-300">|</span>}
                    {specs.bathrooms !== undefined && (
                        <span><span className="font-bold">{specs.bathrooms}</span> baños</span>
                    )}
                    {area > 0 && (
                        <>
                            <span className="text-slate-300">|</span>
                            <span><span className="font-bold">{area.toLocaleString()}</span> m²</span>
                        </>
                    )}
                    <span className="text-slate-500 ml-1">
                        - {listing.listing_type === 'sale' ? 'Venta' : 'Renta'}
                    </span>
                </div>

                {/* Time Since Published */}
                {timeSinceText && (
                    <div className="flex items-center gap-1 text-[11px] text-slate-400 mb-2">
                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        {timeSinceText}
                    </div>
                )}

                {/* Location Tags */}
                <div className="flex flex-wrap gap-1.5 mb-3 mt-2">
                    {locationTags.map((tag, idx) => (
                        <span
                            key={idx}
                            className="bg-slate-100 text-slate-600 text-[11px] font-medium px-2 py-0.5 rounded"
                        >
                            {tag}
                        </span>
                    ))}
                </div>
            </div>
        </article>
    );
}
