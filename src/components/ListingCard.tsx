'use client';

import { ListingCardData, ListingSpecs, ListingLocation } from '@/types/listing';

interface ListingCardProps {
    listing: ListingCardData;
    onClick: () => void;
}

function formatPrice(price: number): string {
    if (!price) return 'N/A';
    return '$' + price.toLocaleString('en-US');
}

function getArea(specs: ListingSpecs | null | undefined): number {
    if (!specs) return 0;
    const areaStr = specs['Área construida (m²)'] || specs['area'] || specs['m2'] || specs['metros'] || '0';
    return parseFloat(String(areaStr).replace(/[^\d.]/g, '')) || 0;
}

function getImageUrl(images: string[] | null | undefined): string {
    if (!images || images.length === 0) {
        return 'https://via.placeholder.com/400x200?text=Sin+Imagen';
    }
    // Handle JSONB array that might be stringified
    const firstImage = Array.isArray(images) ? images[0] : images;
    return firstImage || 'https://via.placeholder.com/400x200?text=Sin+Imagen';
}

function getMunicipio(location: ListingLocation | undefined): string | undefined {
    if (typeof location === 'object' && location !== null) {
        return location.municipio_detectado;
    }
    return undefined;
}

export default function ListingCard({ listing, onClick }: ListingCardProps) {
    const area = getArea(listing.specs);
    const pricePerM2 = area > 0 && listing.price > 0 ? Math.round(listing.price / area) : null;
    const municipio = getMunicipio(listing.location);

    return (
        <div
            className="group bg-white rounded-xl shadow-sm border border-slate-200 hover:shadow-lg transition-all cursor-pointer flex flex-col overflow-hidden relative"
            onClick={onClick}
        >
            {/* Image Section with Overlays */}
            <div className="relative h-48 overflow-hidden">
                <img
                    src={getImageUrl(listing.images)}
                    alt={listing.title || 'Propiedad'}
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                    onError={(e) => {
                        (e.target as HTMLImageElement).src = 'https://via.placeholder.com/400x200?text=Sin+Imagen';
                    }}
                />

                {/* Top-left Labels */}
                <div className="absolute top-3 left-3 flex flex-col gap-1.5 pointer-events-none">
                    <span className="bg-white/90 backdrop-blur-sm text-[var(--text-primary)] text-[10px] font-bold px-2 py-0.5 rounded shadow-sm border border-slate-100 uppercase tracking-wider">
                        {listing.listing_type === 'sale' ? 'En Venta' : 'En Renta'}
                    </span>
                    {listing.price > 1000000 && (
                        <span className="bg-blue-600 text-white text-[10px] font-bold px-2 py-0.5 rounded shadow-sm uppercase tracking-wider">
                            Premium
                        </span>
                    )}
                </div>

                {/* Top-right Heart (Save) */}
                <button className="absolute top-3 right-3 p-1.5 rounded-full bg-black/10 hover:bg-black/20 text-white transition-colors">
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
                    </svg>
                </button>

                {/* Bottom-right Logo Mockup */}
                <div className="absolute bottom-2 right-2 bg-white/80 backdrop-blur-sm px-1.5 py-0.5 rounded text-[8px] font-black italic tracking-tighter text-blue-900 border border-slate-100">
                    CHIVO<span className="text-blue-600">CASA</span>
                </div>
            </div>

            <div className="p-3 flex-1 flex flex-col">
                {/* Price and Options */}
                <div className="flex justify-between items-start mb-1">
                    <div className="text-xl font-extrabold text-[#272727] tracking-tight">
                        {formatPrice(listing.price)}
                        {listing.listing_type === 'rent' && (
                            <span className="text-sm font-normal text-slate-500 ml-1">/mo</span>
                        )}
                    </div>
                    <button className="text-blue-500 hover:text-blue-700 p-0.5">
                        <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                            <path d="M6 10a2 2 0 11-4 0 2 2 0 014 0zM12 10a2 2 0 11-4 0 2 2 0 014 0zM16 12a2 2 0 100-4 2 2 0 000 4z" />
                        </svg>
                    </button>
                </div>

                {/* Specs Inline Row */}
                <div className="flex items-center gap-1.5 text-[13px] text-slate-700 font-medium mb-1">
                    {listing.specs?.bedrooms && (
                        <span><span className="font-bold">{listing.specs.bedrooms}</span> hab</span>
                    )}
                    {(listing.specs?.bedrooms && listing.specs?.bathrooms) && <span className="text-slate-300">|</span>}
                    {listing.specs?.bathrooms && (
                        <span><span className="font-bold">{listing.specs.bathrooms}</span> baños</span>
                    )}
                    {area > 0 && <span className="text-slate-300">|</span>}
                    {area > 0 && (
                        <span><span className="font-bold">{area.toLocaleString()}</span> m²</span>
                    )}
                    <span className="text-slate-400 font-normal"> - {listing.listing_type === 'sale' ? 'Venta' : 'Renta'}</span>
                </div>

                {/* Title / Address */}
                <div className="text-[13px] text-slate-500 leading-tight mb-3">
                    <h6 className="truncate font-normal" title={listing.title}>
                        {listing.title || 'Propiedad sin dirección especificada'}
                    </h6>
                    {municipio && (
                        <span className="text-[11px] text-slate-400 uppercase tracking-wide">
                            {municipio}, El Salvador
                        </span>
                    )}
                </div>

                {/* Footer / Agency */}
                <div className="mt-auto pt-2 border-t border-slate-50 flex items-center justify-between">
                    <span className="text-[10px] text-slate-400 font-medium uppercase tracking-tighter">
                        RE/MAX Central Group
                    </span>
                    <span className="text-[9px] text-slate-300 font-mono">
                        ID: {listing.external_id}
                    </span>
                </div>
            </div>
        </div>
    );
}
