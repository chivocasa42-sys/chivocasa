'use client';

interface ListingCardProps {
    listing: {
        external_id: number;
        title: string;
        price: number;
        listing_type: 'sale' | 'rent';
        images?: string[] | null;
        specs?: Record<string, string | number> | null;
        location?: {
            municipio_detectado?: string;
            departamento?: string;
        } | null;
    };
    onClick: () => void;
}

function formatPrice(price: number): string {
    if (!price) return 'N/A';
    return '$' + price.toLocaleString('en-US');
}

function getArea(specs: Record<string, string | number> | null | undefined): number {
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

export default function ListingCard({ listing, onClick }: ListingCardProps) {
    const area = getArea(listing.specs);
    const pricePerM2 = area > 0 && listing.price > 0 ? Math.round(listing.price / area) : null;
    const municipio = listing.location?.municipio_detectado;

    return (
        <div
            className="bg-white rounded-xl shadow-sm border border-slate-200 hover:shadow-md hover:border-[var(--primary)] transition-all cursor-pointer flex flex-col overflow-hidden"
            onClick={onClick}
        >
            <img
                src={getImageUrl(listing.images)}
                alt={listing.title || 'Propiedad'}
                className="w-full h-48 object-cover"
                onError={(e) => {
                    (e.target as HTMLImageElement).src = 'https://via.placeholder.com/400x200?text=Sin+Imagen';
                }}
            />
            <div className="p-4 flex-1 flex flex-col">
                <h6 className="font-semibold text-slate-800 truncate mb-2" title={listing.title}>
                    {listing.title || 'Propiedad sin título'}
                </h6>

                <div className="text-2xl font-bold text-[var(--primary)] mb-2">
                    {formatPrice(listing.price)}
                    {listing.listing_type === 'rent' && (
                        <span className="text-sm font-normal text-slate-400">/mes</span>
                    )}
                </div>

                <div className="flex flex-wrap gap-2 mb-3">
                    {listing.specs?.bedrooms && (
                        <span className="inline-flex items-center gap-1 bg-slate-100 text-slate-600 text-xs font-medium px-2 py-1 rounded">
                            🛏️ {listing.specs.bedrooms}
                        </span>
                    )}
                    {listing.specs?.bathrooms && (
                        <span className="inline-flex items-center gap-1 bg-slate-100 text-slate-600 text-xs font-medium px-2 py-1 rounded">
                            🚿 {listing.specs.bathrooms}
                        </span>
                    )}
                    {area > 0 && (
                        <span className="inline-flex items-center gap-1 bg-slate-100 text-slate-600 text-xs font-medium px-2 py-1 rounded">
                            📐 {area} m²
                        </span>
                    )}
                </div>

                <div className="mt-auto flex items-center justify-between">
                    {municipio && (
                        <span className="text-xs text-slate-500 truncate max-w-[60%]">
                            📍 {municipio}
                        </span>
                    )}
                    <span className={`text-xs font-medium px-2 py-0.5 rounded ${listing.listing_type === 'sale'
                        ? 'bg-emerald-100 text-emerald-700'
                        : 'bg-blue-100 text-blue-700'
                        }`}>
                        {listing.listing_type === 'sale' ? 'Venta' : 'Alquiler'}
                    </span>
                </div>
            </div>
        </div>
    );
}
