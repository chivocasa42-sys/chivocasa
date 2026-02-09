'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import dynamic from 'next/dynamic';
import SectionHeader from './SectionHeader';
import ListingModal from './ListingModal';

// Dynamically import Leaflet components to avoid SSR issues
const MapContainer = dynamic(
    () => import('react-leaflet').then((mod) => mod.MapContainer),
    { ssr: false }
);
const TileLayer = dynamic(
    () => import('react-leaflet').then((mod) => mod.TileLayer),
    { ssr: false }
);
const Marker = dynamic(
    () => import('react-leaflet').then((mod) => mod.Marker),
    { ssr: false }
);
const Circle = dynamic(
    () => import('react-leaflet').then((mod) => mod.Circle),
    { ssr: false }
);

// San Salvador default coordinates
const DEFAULT_CENTER: [number, number] = [13.6929, -89.2182];
const DEFAULT_ZOOM = 12;
const LISTINGS_PER_PAGE = 3;

interface SearchResult {
    display_name: string;
    lat: string;
    lon: string;
}

interface PriceStats {
    listing_type: 'sale' | 'rent';
    listings_count: number;
    avg_price: string;
    median_price: string;
    min_price: string;
    max_price: string;
}

interface NearbyListing {
    external_id: string | number;
    listing_type: 'sale' | 'rent';
    price: number;
    last_updated: string;
    title: string;
    url: string;
    source: string;
    lat: number;
    lng: number;
    distance_km: string;
    total_count: number;
    // Extended fields from JSONB
    specs: {
        bedrooms?: number | null;
        bathrooms?: number | null;
        area_m2?: number | null;
    } | null;
    tags: string[] | null;
    first_image: string | null;
}

interface PaginationInfo {
    total_count: number;
    limit: number;
    offset: number;
    has_more: boolean;
}

interface NearbyData {
    stats: PriceStats[];
    listings: NearbyListing[];
    pagination: PaginationInfo;
    meta: {
        lat: number;
        lng: number;
        radius_km: number;
        sort_by: string;
    };
}

type SortOption = 'distance_asc' | 'recent' | 'price_asc' | 'price_desc';
type ListingTypeFilter = 'sale' | 'rent';

interface MapExplorerProps {
    externalLocation?: { lat: number; lng: number; name: string } | null;
}

// Map click handler component
function MapClickHandler({ onMapClick }: { onMapClick: (lat: number, lng: number) => void }) {
    const MapEvents = require('react-leaflet').useMapEvents;
    MapEvents({
        click(e: any) {
            onMapClick(e.latlng.lat, e.latlng.lng);
        },
    });
    return null;
}

// Fly to new center when mapCenter changes (MapContainer ignores center prop after init)
function MapCenterUpdater({ center }: { center: [number, number] }) {
    const useMap = require('react-leaflet').useMap;
    const map = useMap();
    useEffect(() => {
        map.flyTo(center, 14, { duration: 1 });
    }, [center, map]);
    return null;
}

function formatPrice(price: string | number): string {
    const num = typeof price === 'string' ? parseFloat(price) : price;
    if (isNaN(num)) return 'N/A';
    return '$' + num.toLocaleString('en-US');
}

function formatPriceShort(price: string | number): string {
    const num = typeof price === 'string' ? parseFloat(price) : price;
    if (isNaN(num)) return 'N/A';
    if (num >= 1000000) return `$${(num / 1000000).toFixed(1)}M`;
    if (num >= 1000) return `$${Math.round(num / 1000)}K`;
    return `$${num.toLocaleString()}`;
}

const SORT_OPTIONS: { value: SortOption; label: string }[] = [
    { value: 'distance_asc', label: 'Más cercanas' },
    { value: 'recent', label: 'Más recientes' },
    { value: 'price_asc', label: 'Precio ↑' },
    { value: 'price_desc', label: 'Precio ↓' },
];

export default function MapExplorer({ externalLocation }: MapExplorerProps) {
    const [selectedLocation, setSelectedLocation] = useState<{ lat: number; lng: number } | null>(null);
    const [radius, setRadius] = useState(1.5);
    const [searchQuery, setSearchQuery] = useState('');
    const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
    const [isSearching, setIsSearching] = useState(false);
    const [nearbyData, setNearbyData] = useState<NearbyData | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [mapCenter, setMapCenter] = useState<[number, number]>(DEFAULT_CENTER);
    const [mapReady, setMapReady] = useState(false);

    // Pagination, sorting & filtering state
    const [sortBy, setSortBy] = useState<SortOption>('distance_asc');
    const [currentPage, setCurrentPage] = useState(0);
    const [isPaginating, setIsPaginating] = useState(false);
    const [activeTab, setActiveTab] = useState<ListingTypeFilter>('sale');

    // Modal state
    const [selectedListingId, setSelectedListingId] = useState<string | number | null>(null);

    // Auto-fetch trigger: incremented when a search result is selected
    const [autoFetchTrigger, setAutoFetchTrigger] = useState(0);

    const searchTimeoutRef = useRef<NodeJS.Timeout | null>(null);

    // React to external location from hero search bar
    useEffect(() => {
        if (externalLocation) {
            setSelectedLocation({ lat: externalLocation.lat, lng: externalLocation.lng });
            setMapCenter([externalLocation.lat, externalLocation.lng]);
            setSearchQuery(externalLocation.name);
            setNearbyData(null);
            setError(null);
            setCurrentPage(0);
            setAutoFetchTrigger(prev => prev + 1);
        }
    }, [externalLocation]);

    // Handle map click
    const handleMapClick = useCallback((lat: number, lng: number) => {
        setSelectedLocation({ lat, lng });
        setNearbyData(null);
        setError(null);
        setCurrentPage(0);
    }, []);

    // Search places using Nominatim
    const searchPlaces = useCallback(async (query: string) => {
        if (!query.trim() || query.length < 3) {
            setSearchResults([]);
            return;
        }

        setIsSearching(true);
        try {
            const response = await fetch(`/api/geocode?q=${encodeURIComponent(query)}`);

            if (response.ok) {
                const data: SearchResult[] = await response.json();
                setSearchResults(data);
            }
        } catch (err) {
            console.error('Search error:', err);
        } finally {
            setIsSearching(false);
        }
    }, []);

    // Debounced search
    const handleSearchInput = useCallback((value: string) => {
        setSearchQuery(value);

        if (searchTimeoutRef.current) {
            clearTimeout(searchTimeoutRef.current);
        }

        searchTimeoutRef.current = setTimeout(() => {
            searchPlaces(value);
        }, 500);
    }, [searchPlaces]);

    // Select a search result
    const selectSearchResult = useCallback((result: SearchResult) => {
        const lat = parseFloat(result.lat);
        const lng = parseFloat(result.lon);
        setSelectedLocation({ lat, lng });
        setMapCenter([lat, lng]);
        setSearchQuery(result.display_name.split(',')[0]);
        setSearchResults([]);
        setNearbyData(null);
        setError(null);
        setCurrentPage(0);
        setAutoFetchTrigger(prev => prev + 1);
    }, []);

    // Fetch nearby listings with pagination
    const fetchNearbyListings = useCallback(async (page: number = 0, isPageChange: boolean = false, listingType?: ListingTypeFilter) => {
        if (!selectedLocation) return;

        if (isPageChange) {
            setIsPaginating(true);
        } else {
            setIsLoading(true);
            setNearbyData(null);
        }
        setError(null);

        try {
            const offset = page * LISTINGS_PER_PAGE;
            const typeToFetch = listingType || activeTab;
            const response = await fetch(
                `/api/nearby-listings?lat=${selectedLocation.lat}&lng=${selectedLocation.lng}&radius=${radius}&sort_by=${sortBy}&limit=${LISTINGS_PER_PAGE}&offset=${offset}&listing_type=${typeToFetch}`
            );

            if (!response.ok) {
                throw new Error('Error al obtener listados');
            }

            const data: NearbyData = await response.json();
            setNearbyData(data);
            setCurrentPage(page);
        } catch (err) {
            console.error('Fetch error:', err);
            setError('No se pudieron cargar los listados cercanos');
        } finally {
            setIsLoading(false);
            setIsPaginating(false);
        }
    }, [selectedLocation, radius, sortBy, activeTab]);

    // Auto-fetch when a search result is selected (from hero or map explorer search)
    useEffect(() => {
        if (autoFetchTrigger > 0 && selectedLocation) {
            fetchNearbyListings(0, false);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [autoFetchTrigger]);

    // Handle tab change
    const handleTabChange = useCallback((tab: ListingTypeFilter) => {
        setActiveTab(tab);
        setCurrentPage(0);
        if (nearbyData) {
            fetchNearbyListings(0, false, tab);
        }
    }, [nearbyData, fetchNearbyListings]);

    // Navigate pages
    const goToNextPage = useCallback(() => {
        if (nearbyData?.pagination.has_more) {
            fetchNearbyListings(currentPage + 1, true);
        }
    }, [nearbyData, currentPage, fetchNearbyListings]);

    const goToPrevPage = useCallback(() => {
        if (currentPage > 0) {
            fetchNearbyListings(currentPage - 1, true);
        }
    }, [currentPage, fetchNearbyListings]);

    // Fix Leaflet default marker icon
    useEffect(() => {
        if (typeof window !== 'undefined') {
            const L = require('leaflet');
            delete (L.Icon.Default.prototype as any)._getIconUrl;
            L.Icon.Default.mergeOptions({
                iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
                iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
                shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
            });
            setMapReady(true);
        }
    }, []);

    const saleStats = nearbyData?.stats.find(s => s.listing_type === 'sale');
    const rentStats = nearbyData?.stats.find(s => s.listing_type === 'rent');
    const totalCount = nearbyData?.pagination.total_count || 0;
    const totalPages = Math.ceil(totalCount / LISTINGS_PER_PAGE);

    return (
        <>
            <div className="mb-8" id="explorar-mapa">
                <SectionHeader
                    title={['Explorar', 'por ubicación']}
                    subtitle="Busca una ubicación y encuentra propiedades cercanas con estadísticas de precios"
                />

                {/* Side-by-side layout */}
                <div className="flex flex-col lg:flex-row gap-4">
                    {/* Left: Map & Controls */}
                    <div className="flex-1 lg:w-1/2">
                        <div className="card-float p-4 h-full">
                            {/* Search Bar */}
                            <div className="mb-3 relative">
                                <input
                                    type="text"
                                    placeholder="Buscar lugar (Santa Tecla, Escalón...)"
                                    value={searchQuery}
                                    onChange={(e) => handleSearchInput(e.target.value)}
                                    className="w-full px-4 py-2 rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] text-[var(--text-primary)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)] focus:border-transparent"
                                />
                                {isSearching && (
                                    <div className="absolute right-3 top-1/2 -translate-y-1/2">
                                        <div className="w-4 h-4 border-2 border-[var(--primary)] border-t-transparent rounded-full animate-spin"></div>
                                    </div>
                                )}

                                {/* Search Results Dropdown */}
                                {searchResults.length > 0 && (
                                    <div className="absolute z-50 w-full mt-1 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg shadow-lg max-h-48 overflow-y-auto">
                                        {searchResults.map((result, idx) => (
                                            <button
                                                key={idx}
                                                onClick={() => selectSearchResult(result)}
                                                className="w-full px-3 py-2 text-left hover:bg-[var(--bg-subtle)] transition-colors border-b border-[var(--border-color)] last:border-b-0 text-sm"
                                            >
                                                <span className="text-[var(--text-primary)] line-clamp-1">
                                                    {result.display_name}
                                                </span>
                                            </button>
                                        ))}
                                    </div>
                                )}
                            </div>

                            {/* Map Container - z-index lower than modal */}
                            <div className="rounded-lg overflow-hidden border border-[var(--border-color)] mb-3 relative h-[240px] md:h-[320px]" style={{ zIndex: 0 }}>
                                {mapReady && (
                                    <MapContainer
                                        center={mapCenter}
                                        zoom={DEFAULT_ZOOM}
                                        style={{ height: '100%', width: '100%' }}
                                        scrollWheelZoom={true}
                                    >
                                        <TileLayer
                                            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                                            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                                        />
                                        <MapClickHandler onMapClick={handleMapClick} />
                                        <MapCenterUpdater center={mapCenter} />

                                        {selectedLocation && (
                                            <>
                                                <Marker position={[selectedLocation.lat, selectedLocation.lng]} />
                                                <Circle
                                                    center={[selectedLocation.lat, selectedLocation.lng]}
                                                    radius={radius * 1000}
                                                    pathOptions={{
                                                        color: 'var(--primary)',
                                                        fillColor: 'var(--primary)',
                                                        fillOpacity: 0.15,
                                                        weight: 2
                                                    }}
                                                />
                                            </>
                                        )}
                                    </MapContainer>
                                )}
                            </div>

                            {/* Controls: Radius + Sort + Button */}
                            <div className="space-y-3">
                                {/* Radius Slider */}
                                <div className="flex items-center gap-2">
                                    <label className="text-xs text-[var(--text-secondary)] whitespace-nowrap">Radio:</label>
                                    <input
                                        type="range"
                                        min="0.5"
                                        max="10"
                                        step="0.5"
                                        value={radius}
                                        onChange={(e) => setRadius(parseFloat(e.target.value))}
                                        className="flex-1 accent-[var(--primary)] h-1"
                                    />
                                    <span className="text-xs font-semibold text-[var(--primary)] min-w-[3rem] text-right">
                                        {radius} km
                                    </span>
                                </div>

                                {/* Button */}
                                <button
                                    onClick={() => fetchNearbyListings(0, false)}
                                    disabled={!selectedLocation || isLoading}
                                    className={`w-full btn-primary px-4 py-2.5 md:py-1.5 rounded-lg text-sm font-semibold transition-all ${!selectedLocation
                                        ? 'opacity-50 cursor-not-allowed'
                                        : 'hover:shadow-lg'
                                        }`}
                                >
                                    {isLoading ? 'Buscando...' : 'Ver Listados'}
                                </button>
                            </div>
                        </div>
                    </div>

                    {/* Right: Results Panel */}
                    <div className="flex-1 lg:w-1/2">
                        <div className="card-float p-3 md:p-4 h-full min-h-[300px] md:min-h-[480px]">
                            {/* Tabs: VENTA | ALQUILER */}
                            <div className="flex border-b border-[var(--border-color)] mb-4">
                                <button
                                    onClick={() => handleTabChange('sale')}
                                    className={`flex-1 px-4 py-2.5 text-sm font-semibold transition-all relative ${activeTab === 'sale'
                                        ? 'text-emerald-600'
                                        : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                                        }`}
                                >
                                    <span className="flex items-center justify-center gap-2">
                                        🏠 VENTA
                                        {saleStats && (
                                            <span className="text-xs bg-emerald-100 text-emerald-700 px-1.5 py-0.5 rounded-full">
                                                {saleStats.listings_count}
                                            </span>
                                        )}
                                    </span>
                                    {activeTab === 'sale' && (
                                        <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-emerald-500"></div>
                                    )}
                                </button>
                                <button
                                    onClick={() => handleTabChange('rent')}
                                    className={`flex-1 px-4 py-2.5 text-sm font-semibold transition-all relative ${activeTab === 'rent'
                                        ? 'text-blue-600'
                                        : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                                        }`}
                                >
                                    <span className="flex items-center justify-center gap-2">
                                        🔑 ALQUILER
                                        {rentStats && (
                                            <span className="text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded-full">
                                                {rentStats.listings_count}
                                            </span>
                                        )}
                                    </span>
                                    {activeTab === 'rent' && (
                                        <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-500"></div>
                                    )}
                                </button>
                            </div>

                            {/* Error Message */}
                            {error && (
                                <div className="p-3 bg-red-100 border border-red-300 rounded-lg text-red-700 text-sm mb-4">
                                    {error}
                                </div>
                            )}

                            {/* Initial Empty State */}
                            {!nearbyData && !isLoading && !error && (
                                <div className="flex flex-col items-center justify-center py-12 text-center">
                                    <div className="w-16 h-16 bg-[var(--bg-subtle)] rounded-full flex items-center justify-center mb-4">
                                        <span className="text-3xl">🗺️</span>
                                    </div>
                                    <h4 className="text-base font-semibold text-[var(--text-primary)] mb-2">
                                        Selecciona una ubicación
                                    </h4>
                                    <p className="text-sm text-[var(--text-muted)] max-w-xs">
                                        Haz clic en el mapa o busca un lugar para ver propiedades cercanas con precios y estadísticas
                                    </p>
                                    {selectedLocation && (
                                        <button
                                            onClick={() => fetchNearbyListings(0, false)}
                                            className="mt-4 btn-primary px-4 py-2 rounded-lg text-sm font-semibold"
                                        >
                                            Ver Listados en esta ubicación
                                        </button>
                                    )}
                                </div>
                            )}

                            {/* Loading State */}
                            {isLoading && (
                                <div className="flex flex-col items-center justify-center py-12">
                                    <div className="w-10 h-10 border-3 border-[var(--primary)] border-t-transparent rounded-full animate-spin mb-4"></div>
                                    <p className="text-sm text-[var(--text-muted)]">Buscando propiedades cercanas...</p>
                                </div>
                            )}

                            {/* Results */}
                            {nearbyData && !isLoading && (
                                <div className="space-y-3">
                                    {/* Stats Summary */}
                                    <div className={`p-3 rounded-lg ${activeTab === 'sale'
                                        ? 'bg-gradient-to-r from-emerald-50 to-emerald-100/50 border border-emerald-200'
                                        : 'bg-gradient-to-r from-blue-50 to-blue-100/50 border border-blue-200'
                                        }`}>
                                        {(activeTab === 'sale' ? saleStats : rentStats) ? (
                                            <div className="flex items-center justify-between text-sm">
                                                <div>
                                                    <span className={activeTab === 'sale' ? 'text-emerald-600' : 'text-blue-600'}>
                                                        Precio promedio:
                                                    </span>
                                                    <span className={`font-bold ml-2 ${activeTab === 'sale' ? 'text-emerald-800' : 'text-blue-800'}`}>
                                                        {formatPriceShort((activeTab === 'sale' ? saleStats : rentStats)!.median_price)}
                                                        {activeTab === 'rent' && '/mes'}
                                                    </span>
                                                </div>
                                                <div className={`text-xs ${activeTab === 'sale' ? 'text-emerald-500' : 'text-blue-500'}`}>
                                                    {formatPriceShort((activeTab === 'sale' ? saleStats : rentStats)!.min_price)} - {formatPriceShort((activeTab === 'sale' ? saleStats : rentStats)!.max_price)}
                                                </div>
                                            </div>
                                        ) : (
                                            <p className={`text-sm ${activeTab === 'sale' ? 'text-emerald-600' : 'text-blue-600'}`}>
                                                No hay propiedades en {activeTab === 'sale' ? 'venta' : 'alquiler'} en esta área
                                            </p>
                                        )}
                                    </div>

                                    {/* Listings Header */}
                                    {nearbyData.listings.length > 0 && (
                                        <div className="flex items-center justify-between">
                                            <span className="text-xs text-[var(--text-muted)]">
                                                {totalCount} propiedades
                                            </span>

                                            {/* Pagination */}
                                            {totalPages > 1 && (
                                                <div className="flex items-center gap-1">
                                                    <button
                                                        onClick={goToPrevPage}
                                                        disabled={currentPage === 0 || isPaginating}
                                                        className={`w-7 h-7 flex items-center justify-center rounded-full border transition-all ${currentPage === 0
                                                            ? 'border-gray-200 text-gray-300 cursor-not-allowed'
                                                            : 'border-[var(--border-color)] text-[var(--text-secondary)] hover:bg-[var(--bg-subtle)]'
                                                            }`}
                                                    >
                                                        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                                            <polyline points="15 18 9 12 15 6"></polyline>
                                                        </svg>
                                                    </button>
                                                    <span className="text-xs text-[var(--text-muted)] min-w-[50px] text-center">
                                                        {isPaginating ? '...' : `${currentPage + 1} / ${totalPages}`}
                                                    </span>
                                                    <button
                                                        onClick={goToNextPage}
                                                        disabled={!nearbyData.pagination.has_more || isPaginating}
                                                        className={`w-7 h-7 flex items-center justify-center rounded-full border transition-all ${!nearbyData.pagination.has_more
                                                            ? 'border-gray-200 text-gray-300 cursor-not-allowed'
                                                            : 'border-[var(--border-color)] text-[var(--text-secondary)] hover:bg-[var(--bg-subtle)]'
                                                            }`}
                                                    >
                                                        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                                            <polyline points="9 18 15 12 9 6"></polyline>
                                                        </svg>
                                                    </button>
                                                </div>
                                            )}
                                        </div>
                                    )}

                                    {/* Listings - New Card Style */}
                                    <div className={`space-y-2 transition-opacity duration-200 ${isPaginating ? 'opacity-50' : 'opacity-100'}`}>
                                        {nearbyData.listings.map((listing) => (
                                            <div
                                                key={listing.external_id}
                                                onClick={() => setSelectedListingId(listing.external_id)}
                                                className="group flex gap-3 p-2 rounded-lg bg-[var(--bg-subtle)] hover:bg-white hover:shadow-md transition-all cursor-pointer border border-[var(--border-color)] hover:border-[var(--primary)]"
                                            >
                                                {/* Thumbnail */}
                                                <div className="w-24 h-20 flex-shrink-0 rounded-md overflow-hidden bg-slate-200">
                                                    <img
                                                        src={listing.first_image || '/placeholder.webp'}
                                                        alt=""
                                                        className="w-full h-full object-cover"
                                                        onError={(e) => {
                                                            (e.target as HTMLImageElement).src = '/placeholder.webp';
                                                        }}
                                                    />
                                                </div>

                                                {/* Content */}
                                                <div className="flex-1 min-w-0 flex flex-col justify-between py-0.5">
                                                    {/* Top Row: Price + Badge */}
                                                    <div className="flex items-center justify-between gap-2">
                                                        {/* Price */}
                                                        <span className="text-base font-black text-[#272727]">
                                                            {formatPrice(listing.price)}
                                                        </span>

                                                        {/* Badge */}
                                                        <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold uppercase ${listing.listing_type === 'sale'
                                                            ? 'bg-emerald-100 text-emerald-700'
                                                            : 'bg-blue-100 text-blue-700'
                                                            }`}>
                                                            {listing.listing_type === 'sale' ? 'VENTA' : 'RENTA'}
                                                        </span>
                                                    </div>

                                                    {/* Mid Row: Specs */}
                                                    <div className="flex items-center gap-1.5 text-xs text-slate-600">
                                                        {listing.specs?.bedrooms && (
                                                            <span>
                                                                <span className="font-bold">{listing.specs.bedrooms}</span> hab
                                                            </span>
                                                        )}
                                                        {listing.specs?.bedrooms && listing.specs?.bathrooms && (
                                                            <span className="text-slate-300">|</span>
                                                        )}
                                                        {listing.specs?.bathrooms && (
                                                            <span>
                                                                <span className="font-bold">{listing.specs.bathrooms}</span> baños
                                                            </span>
                                                        )}
                                                        {listing.specs?.area_m2 && (
                                                            <>
                                                                <span className="text-slate-300">|</span>
                                                                <span className="flex items-center gap-0.5">
                                                                    <svg className="w-3 h-3 text-emerald-600" fill="currentColor" viewBox="0 0 20 20">
                                                                        <path d="M3 4a1 1 0 011-1h12a1 1 0 011 1v2a1 1 0 01-1 1H4a1 1 0 01-1-1V4zM3 10a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H4a1 1 0 01-1-1v-6zM14 9a1 1 0 00-1 1v6a1 1 0 001 1h2a1 1 0 001-1v-6a1 1 0 00-1-1h-2z" />
                                                                    </svg>
                                                                    <span className="font-bold">{listing.specs.area_m2}</span> m²
                                                                </span>
                                                            </>
                                                        )}
                                                    </div>

                                                    {/* Bottom Row: Distance + Tags */}
                                                    <div className="flex items-center gap-2 text-xs">
                                                        <span className="font-medium text-[var(--text-muted)]">{parseFloat(listing.distance_km).toFixed(1)} km</span>
                                                        {listing.tags && listing.tags.length > 0 && (
                                                            <>
                                                                <span className="text-[var(--text-muted)]">•</span>
                                                                <div className="flex gap-1 flex-wrap">
                                                                    {listing.tags.slice(0, 2).map((tag, idx) => (
                                                                        <span key={idx} className="bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded text-[10px]">
                                                                            {tag}
                                                                        </span>
                                                                    ))}
                                                                </div>
                                                            </>
                                                        )}
                                                    </div>
                                                </div>
                                            </div>
                                        ))}
                                    </div>

                                    {/* No listings */}
                                    {nearbyData.listings.length === 0 && (
                                        <div className="text-center py-8">
                                            <span className="text-3xl mb-2 block">🏘️</span>
                                            <p className="text-sm text-[var(--text-muted)]">
                                                No hay propiedades en {activeTab === 'sale' ? 'venta' : 'alquiler'} en esta área
                                            </p>
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>

            {/* Modal - same as department page */}
            {selectedListingId && (
                <ListingModal
                    externalId={selectedListingId}
                    onClose={() => setSelectedListingId(null)}
                />
            )}
        </>
    );
}
