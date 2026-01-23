'use client';

import { Listing } from '@/types/listing';

interface ListingCardProps {
    listing: Listing;
    onClick: () => void;
}

function formatPrice(price: number): string {
    if (!price) return 'N/A';
    return '$' + price.toLocaleString('en-US');
}

function getArea(listing: Listing): number {
    const specs = listing.specs || {};
    const areaStr = specs['Área construida (m²)'] || specs['area'] || specs['m2'] || specs['metros'] || '0';
    return parseFloat(String(areaStr).replace(/[^\d.]/g, '')) || 0;
}

export default function ListingCard({ listing, onClick }: ListingCardProps) {
    const area = getArea(listing);
    const pricePerM2 = area > 0 ? Math.round(listing.price / area) : null;

    return (
        <div
            className="card listing-card h-full flex flex-col cursor-pointer"
            onClick={onClick}
        >
            <img
                src={listing.images?.[0] || 'https://via.placeholder.com/400x200?text=No+Image'}
                alt={listing.title}
                className="w-full h-48 object-cover rounded-t-lg"
            />
            <div className="p-4 flex-1">
                <h6 className="font-semibold truncate mb-2" title={listing.title}>
                    {listing.title || 'Untitled'}
                </h6>
                <div className="price-avg mb-2">{formatPrice(listing.price)}</div>
                <div className="flex flex-wrap gap-2 mb-2">
                    {listing.specs?.bedrooms && (
                        <span className="spec-badge">
                            <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 16 16">
                                <path d="M8.354 1.146a.5.5 0 0 0-.708 0l-6 6A.5.5 0 0 0 1.5 7.5v7a.5.5 0 0 0 .5.5h4.5a.5.5 0 0 0 .5-.5v-4h2v4a.5.5 0 0 0 .5.5H14a.5.5 0 0 0 .5-.5v-7a.5.5 0 0 0-.146-.354L13 5.793V2.5a.5.5 0 0 0-.5-.5h-1a.5.5 0 0 0-.5.5v1.293L8.354 1.146z" />
                            </svg>
                            {listing.specs.bedrooms} hab
                        </span>
                    )}
                    {listing.specs?.bathrooms && (
                        <span className="spec-badge">
                            <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 16 16">
                                <path d="M7 14s-1 0-1-1 1-4 5-4 5 3 5 4-1 1-1 1H7zm4-6a3 3 0 1 0 0-6 3 3 0 0 0 0 6z" />
                            </svg>
                            {listing.specs.bathrooms} baño
                        </span>
                    )}
                    {pricePerM2 && (
                        <span className="spec-badge">
                            <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 16 16">
                                <path d="M1 0a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h5v-1H2v-1h4v-1H4v-1h2v-1H2v-1h4V9H4V8h2V7H2V6h4V2h1v4h1V4h1v2h1V2h1v4h1V4h1v2h1V2h1v4h1V1a1 1 0 0 0-1-1H1z" />
                            </svg>
                            ${pricePerM2}/m²
                        </span>
                    )}
                </div>
                <small className="text-muted">
                    {listing.listing_type === 'sale' ? 'Venta' : 'Alquiler'}
                </small>
            </div>
        </div>
    );
}
