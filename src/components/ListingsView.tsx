'use client';

import { useState } from 'react';
import { Listing, LocationStats } from '@/types/listing';
import ListingCard from './ListingCard';
import ListingModal from './ListingModal';

interface ListingsViewProps {
    location: string;
    stats: LocationStats;
    allListings: Listing[];
    onBack: () => void;
}

function getArea(listing: Listing): number {
    const specs = listing.specs || {};
    const areaStr = specs['Área construida (m²)'] || specs['area'] || specs['m2'] || specs['metros'] || '0';
    return parseFloat(String(areaStr).replace(/[^\d.]/g, '')) || 0;
}

type SortOption = 'price-asc' | 'price-desc' | 'rooms-desc' | 'rooms-asc' | 'ppm2-asc' | 'ppm2-desc';

export default function ListingsView({ location, stats, allListings, onBack }: ListingsViewProps) {
    const [sortBy, setSortBy] = useState<SortOption>('price-asc');
    const [selectedListingId, setSelectedListingId] = useState<number | null>(null);

    const sortedListings = [...stats.listings].sort((a, b) => {
        switch (sortBy) {
            case 'price-asc':
                return (a.price || 0) - (b.price || 0);
            case 'price-desc':
                return (b.price || 0) - (a.price || 0);
            case 'rooms-desc':
                return (Number(b.specs?.bedrooms) || 0) - (Number(a.specs?.bedrooms) || 0);
            case 'rooms-asc':
                return (Number(a.specs?.bedrooms) || 0) - (Number(b.specs?.bedrooms) || 0);
            case 'ppm2-asc': {
                const ppmA = getArea(a) > 0 ? (a.price || 0) / getArea(a) : Infinity;
                const ppmB = getArea(b) > 0 ? (b.price || 0) / getArea(b) : Infinity;
                return ppmA - ppmB;
            }
            case 'ppm2-desc': {
                const ppmA = getArea(a) > 0 ? (a.price || 0) / getArea(a) : 0;
                const ppmB = getArea(b) > 0 ? (b.price || 0) / getArea(b) : 0;
                return ppmB - ppmA;
            }
            default:
                return 0;
        }
    });

    return (
        <>
            {/* Breadcrumb */}
            <nav className="breadcrumb mb-4">
                <a href="#" onClick={(e) => { e.preventDefault(); onBack(); }}>Ubicaciones</a>
                <span className="text-gray-400">/</span>
                <span className="text-muted">{location}</span>
            </nav>

            {/* Header */}
            <div className="flex flex-wrap justify-between items-center gap-3 mb-6">
                <h2 className="text-2xl font-bold flex items-center gap-2">
                    <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 16 16">
                        <path d="M14.763.075A.5.5 0 0 1 15 .5v15a.5.5 0 0 1-.5.5h-3a.5.5 0 0 1-.5-.5V14h-1v1.5a.5.5 0 0 1-.5.5h-9a.5.5 0 0 1-.5-.5V10a.5.5 0 0 1 .342-.474L6 7.64V4.5a.5.5 0 0 1 .276-.447l8-4a.5.5 0 0 1 .487.022zM6 8.694 1 10.36V15h5V8.694zM7 15h2v-1.5a.5.5 0 0 1 .5-.5h2a.5.5 0 0 1 .5.5V15h2V1.309l-7 3.5V15z" />
                    </svg>
                    {location} ({stats.count} propiedades)
                </h2>
                <div className="flex items-center gap-2">
                    <label className="text-muted text-sm">Ordenar:</label>
                    <select
                        value={sortBy}
                        onChange={(e) => setSortBy(e.target.value as SortOption)}
                        className="border border-gray-300 rounded px-3 py-1 text-sm bg-white"
                    >
                        <option value="price-asc">Precio ↑</option>
                        <option value="price-desc">Precio ↓</option>
                        <option value="rooms-desc">Habitaciones ↓</option>
                        <option value="rooms-asc">Habitaciones ↑</option>
                        <option value="ppm2-asc">Precio/m² ↑</option>
                        <option value="ppm2-desc">Precio/m² ↓</option>
                    </select>
                </div>
            </div>

            {/* Listings Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {sortedListings.map((listing) => (
                    <ListingCard
                        key={listing.external_id}
                        listing={listing}
                        onClick={() => setSelectedListingId(listing.external_id)}
                    />
                ))}
            </div>

            {/* Modal */}
            {selectedListingId && (
                <ListingModal
                    externalId={selectedListingId}
                    onClose={() => setSelectedListingId(null)}
                />
            )}
        </>
    );
}
