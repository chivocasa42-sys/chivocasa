'use client';

import LazyImage from './LazyImage';

interface ListingCardProps {
    listing: {
        external_id: number;
        title?: string;
        price: number;
        listing_type: 'sale' | 'rent';
        images?: string[] | null;
        specs?: Record<string, string | number | undefined> | null;
        details?: Record<string, string> | null;
        location?: any;
        tags?: string[] | null;
    };
    onClick: () => void;
}

function formatPrice(price: number): string {
    if (!price) return 'N/A';
    return '$' + price.toLocaleString('en-US');
}

function getArea(specs: Record<string, string | number | undefined> | null | undefined): number {
    if (!specs) return 0;
    const areaStr = specs['Área construida (m²)'] || specs['area'] || specs['m2'] || specs['metros'] || '0';
    return parseFloat(String(areaStr).replace(/[^\d.]/g, '')) || 0;
}

function getImageUrl(images: string[] | null | undefined): string {
    if (!images || images.length === 0) {
        return 'https://via.placeholder.com/600x400?text=Sin+Imagen';
    }
    const firstImage = Array.isArray(images) ? images[0] : images;
    return firstImage || 'https://via.placeholder.com/600x400?text=Sin+Imagen';
}

// Get location-based tags from the listing
function getLocationTags(location: ListingCardProps['listing']['location'], tags?: string[] | null): string[] {
    // Prefer the tags array if it exists
    if (tags && tags.length > 0) {
        return tags.slice(0, 3); // Max 3 location tags
    }

    // Fallback to building from location object
    const locationTags: string[] = [];
    if (location) {
        if (location.municipio_detectado) locationTags.push(location.municipio_detectado);
        if (location.departamento) locationTags.push(location.departamento);
    }
    locationTags.push('El Salvador');

    return locationTags.slice(0, 3);
}

export default function ListingCard({ listing, onClick }: ListingCardProps) {
    const area = getArea(listing.specs);
    const locationTags = getLocationTags(listing.location, listing.tags);

    return (
        <div
            className="group bg-white rounded-lg shadow-sm border border-slate-200 hover:shadow-xl transition-all cursor-pointer overflow-hidden"
            onClick={onClick}
        >
            {/* Image Section - Larger aspect ratio */}
            <div className="relative aspect-[4/3] overflow-hidden">
                <LazyImage
                    src={getImageUrl(listing.images)}
                    alt="Propiedad"
                    className="w-full h-full group-hover:scale-105 transition-transform duration-500"
                    placeholderSrc="https://via.placeholder.com/600x400?text=Sin+Imagen"
                />

                {/* Top-left Label */}
                <div className="absolute top-3 left-3">
                    <span className="bg-white/95 backdrop-blur-sm text-slate-800 text-[11px] font-bold px-2.5 py-1 rounded shadow-sm uppercase tracking-wide flex items-center gap-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-red-500"></span>
                        {listing.listing_type === 'sale' ? 'En Venta' : 'En Renta'}
                    </span>
                </div>

                {/* Top-right Heart */}
                <button
                    className="absolute top-3 right-3 p-2 rounded-full bg-white/90 hover:bg-white text-slate-600 hover:text-red-500 transition-colors shadow-sm"
                    onClick={(e) => e.stopPropagation()}
                >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
                    </svg>
                </button>

                {/* Bottom-right Logo */}
                <div className="absolute bottom-2 right-2 bg-white/90 backdrop-blur-sm px-2 py-0.5 rounded text-[9px] font-black italic tracking-tight text-slate-800 shadow-sm">
                    CHIVO<span className="text-blue-600">CASA</span>
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

                {/* Specs Row */}
                <div className="flex items-center gap-2 text-[14px] text-slate-700 mb-3">
                    {listing.specs?.bedrooms && (
                        <>
                            <span><span className="font-bold">{listing.specs.bedrooms}</span> hab</span>
                            <span className="text-slate-300">|</span>
                        </>
                    )}
                    {listing.specs?.bathrooms && (
                        <>
                            <span><span className="font-bold">{listing.specs.bathrooms}</span> baños</span>
                            <span className="text-slate-300">|</span>
                        </>
                    )}
                    {area > 0 && (
                        <span><span className="font-bold">{area.toLocaleString()}</span> m²</span>
                    )}
                    <span className="text-slate-400 ml-1">
                        - {listing.listing_type === 'sale' ? 'Venta' : 'Renta'}
                    </span>
                </div>

                {/* Location Tags */}
                <div className="flex flex-wrap gap-1.5 mb-3">
                    {locationTags.map((tag, idx) => (
                        <span
                            key={idx}
                            className="bg-slate-100 text-slate-600 text-[11px] font-medium px-2 py-0.5 rounded"
                        >
                            {tag}
                        </span>
                    ))}
                </div>

                {/* Footer - Source only, no ID */}
                <div className="pt-2 border-t border-slate-100">
                    <span className="text-[10px] text-slate-400 font-medium uppercase tracking-wide">
                        Fuente: Encuentra24
                    </span>
                </div>
            </div>
        </div>
    );
}
