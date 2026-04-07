'use client';

import 'leaflet/dist/leaflet.css';
import { useCallback, useEffect, useRef, useState } from 'react';
import dynamic from 'next/dynamic';
import { useMap, useMapEvents } from 'react-leaflet';
import type { Listing } from '@/types/listing';
import ListingCard from './ListingCard';
import ListingModal from './ListingModal';

const MapContainer = dynamic(() => import('react-leaflet').then((mod) => mod.MapContainer), { ssr: false });
const TileLayer = dynamic(() => import('react-leaflet').then((mod) => mod.TileLayer), { ssr: false });
const Marker = dynamic(() => import('react-leaflet').then((mod) => mod.Marker), { ssr: false });
const Circle = dynamic(() => import('react-leaflet').then((mod) => mod.Circle), { ssr: false });

const DEFAULT_CENTER: [number, number] = [13.6929, -89.2182];
const DEFAULT_LOCATION = { lat: 13.6929, lng: -89.2182 };
const DEFAULT_LOCATION_NAME = 'San Salvador';
const DEFAULT_ZOOM = 12;
const PAGE_SIZE = 12;

type SortOption = 'distance_asc' | 'recent' | 'price_asc' | 'price_desc';
type ListingTypeFilter = 'sale' | 'rent';

interface SearchResult {
    display_name: string;
    lat: string;
    lon: string;
}

interface PriceStats {
    listing_type: ListingTypeFilter;
    listings_count: number;
    avg_price: string;
    median_price: string;
    min_price: string;
    max_price: string;
}

interface NearbyListing {
    external_id: string | number;
    listing_type: ListingTypeFilter;
    price: number;
    title: string;
    url: string;
    source: string;
    lat: number;
    lng: number;
    distance_km: string;
    total_count: number;
    specs: { bedrooms?: number | null; bathrooms?: number | null; area_m2?: number | null; parking?: number | null } | null;
    tags: string[] | null;
    first_image: string | null;
    published_date?: string | null;
    last_updated: string | null;
}

interface NearbyData {
    stats: PriceStats[];
    listings: NearbyListing[];
    pagination: { total_count: number; limit: number; offset: number; has_more: boolean };
    meta: { lat: number; lng: number; radius_km: number; sort_by: string };
}

interface MapExplorerProps {
    externalLocation?: { lat: number; lng: number; name: string } | null;
}

interface FetchOptions {
    page?: number;
    append?: boolean;
    listingType?: ListingTypeFilter;
    sort?: SortOption;
    scrollToResults?: boolean;
}

interface SearchControlsProps {
    searchQuery: string;
    isSearching: boolean;
    searchResults: SearchResult[];
    isLoading: boolean;
    disabled: boolean;
    variant: 'mobile' | 'desktop';
    onInputChange: (value: string) => void;
    onSelectResult: (result: SearchResult) => void;
    onSearch: () => void;
}

const SORT_OPTIONS: { value: SortOption; label: string }[] = [
    { value: 'distance_asc', label: 'Más cercanas' },
    { value: 'recent', label: 'Más recientes' },
    { value: 'price_asc', label: 'Menor precio' },
    { value: 'price_desc', label: 'Mayor precio' },
];

function SearchControls({
    searchQuery,
    isSearching,
    searchResults,
    isLoading,
    disabled,
    variant,
    onInputChange,
    onSelectResult,
    onSearch,
}: SearchControlsProps) {
    const isMobile = variant === 'mobile';

    return (
        <div
            className={
                isMobile
                    ? 'space-y-3 rounded-[24px] border border-slate-200 bg-slate-50 p-4 shadow-sm'
                    : 'pointer-events-auto space-y-3'
            }
        >
            {isMobile ? (
                <div className="space-y-1">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                        Buscar zona
                    </p>
                    <p className="text-sm leading-relaxed text-slate-600">
                        En movil puedes buscar una colonia o municipio sin abrir
                        el mapa.
                    </p>
                </div>
            ) : null}

            <div className="relative">
                <input
                    value={searchQuery}
                    onChange={(event) => onInputChange(event.target.value)}
                    onKeyDown={(event) => {
                        if (event.key !== 'Enter') return;
                        event.preventDefault();
                        if (searchResults.length > 0) {
                            onSelectResult(searchResults[0]);
                            return;
                        }
                        onSearch();
                    }}
                    placeholder="Buscar lugar o colonia"
                    aria-label="Buscar lugar en el mapa"
                    autoComplete="off"
                    name={`${variant}-location-search`}
                    className={`w-full rounded-2xl border px-4 py-2.5 font-medium text-slate-700 outline-none transition focus:border-[var(--primary)] focus:ring-2 focus:ring-[var(--primary)]/15 ${
                        isMobile
                            ? 'border-slate-200 bg-white text-base shadow-sm'
                            : 'border-white/60 bg-white/95 text-[13px] shadow-lg backdrop-blur-sm'
                    }`}
                />
                {isSearching ? (
                    <div className="absolute right-4 top-1/2 -translate-y-1/2">
                        <div className="h-4 w-4 animate-spin rounded-full border-2 border-[var(--primary)] border-t-transparent" />
                    </div>
                ) : null}
                {searchResults.length > 0 ? (
                    <div className="absolute left-0 right-0 top-[calc(100%+0.5rem)] z-10 max-h-[280px] overflow-y-auto rounded-2xl border border-slate-200 bg-white shadow-2xl">
                        {searchResults.map((result, index) => (
                            <button
                                key={`${result.lat}-${result.lon}-${index}`}
                                type="button"
                                onClick={() => onSelectResult(result)}
                                className="block w-full border-b border-slate-100 px-4 py-3 text-left text-sm text-slate-700 transition hover:bg-slate-50 last:border-b-0"
                            >
                                {result.display_name}
                            </button>
                        ))}
                    </div>
                ) : null}
            </div>

            <div
                className={
                    isMobile
                        ? 'flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between'
                        : 'flex justify-center'
                }
            >
                {isMobile ? (
                    <p className="text-xs leading-relaxed text-slate-500">
                        Carga inmuebles alrededor del punto seleccionado.
                    </p>
                ) : null}
                <button
                    type="button"
                    onClick={onSearch}
                    disabled={disabled || isLoading}
                    className={`inline-flex items-center gap-2 rounded-2xl px-4 py-2.5 text-[13px] font-semibold text-white shadow-xl transition ${
                        isMobile ? 'w-full justify-center sm:w-auto' : ''
                    } ${
                        disabled || isLoading
                            ? 'cursor-not-allowed bg-slate-400'
                            : 'bg-slate-900 hover:-translate-y-0.5 hover:bg-slate-800'
                    }`}
                >
                    <svg
                        className="h-4 w-4"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        aria-hidden="true"
                    >
                        <circle cx="11" cy="11" r="7" />
                        <path d="m20 20-3-3" strokeLinecap="round" />
                    </svg>
                    {isLoading ? 'Buscando...' : 'Buscar en esta zona'}
                </button>
            </div>
        </div>
    );
}

function MapClickHandler({ onMapClick }: { onMapClick: (lat: number, lng: number) => void }) {
    useMapEvents({ click: (event: { latlng: { lat: number; lng: number } }) => onMapClick(event.latlng.lat, event.latlng.lng) });
    return null;
}

function MapCenterUpdater({ center }: { center: [number, number] }) {
    const map = useMap();
    useEffect(() => {
        if (!Number.isFinite(center[0]) || !Number.isFinite(center[1])) return;
        map.flyTo(center, 14, { duration: 1 });
    }, [center, map]);
    return null;
}

function formatPrice(value: string | number) {
    const num = typeof value === 'string' ? parseFloat(value) : value;
    if (!Number.isFinite(num)) return 'N/A';
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(num);
}

function formatPriceShort(value: string | number) {
    const num = typeof value === 'string' ? parseFloat(value) : value;
    if (!Number.isFinite(num)) return 'N/A';
    if (num >= 1000000) return `$${(num / 1000000).toFixed(1)}M`;
    if (num >= 1000) return `$${Math.round(num / 1000)}K`;
    return `$${num.toLocaleString('en-US')}`;
}

function headingFor(type: ListingTypeFilter, locationName: string) {
    return type === 'sale' ? `Inmuebles en venta en ${locationName}` : `Inmuebles en renta en ${locationName}`;
}

function mergeListings(current: NearbyListing[], next: NearbyListing[]) {
    const seen = new Set<string>();
    return [...current, ...next].filter((listing) => {
        const key = String(listing.external_id);
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
    });
}

function toListingCardData(listing: NearbyListing, locationName: string): Listing {
    const normalizedSpecs = listing.specs
        ? {
              bedrooms: listing.specs.bedrooms ?? undefined,
              bathrooms: listing.specs.bathrooms ?? undefined,
              area_m2: listing.specs.area_m2 ?? undefined,
              parking: listing.specs.parking ?? undefined,
          }
        : undefined;

    return {
        external_id: listing.external_id,
        title: listing.title,
        price: listing.price,
        listing_type: listing.listing_type,
        url: listing.url,
        source: listing.source,
        tags: null,
        images: listing.first_image ? [listing.first_image] : [],
        location: {
            municipio_detectado: locationName,
            latitude: listing.lat,
            longitude: listing.lng,
        },
        specs: normalizedSpecs,
        published_date: listing.published_date ?? undefined,
        last_updated: listing.last_updated ?? undefined,
    };
}

export default function MapExplorer({ externalLocation }: MapExplorerProps) {
    const [selectedLocation, setSelectedLocation] = useState<{ lat: number; lng: number } | null>(DEFAULT_LOCATION);
    const [selectedLocationName, setSelectedLocationName] = useState(DEFAULT_LOCATION_NAME);
    const [selectedListingId, setSelectedListingId] = useState<string | number | null>(null);
    const [searchQuery, setSearchQuery] = useState(DEFAULT_LOCATION_NAME);
    const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
    const [radius, setRadius] = useState(1.5);
    const [mapCenter, setMapCenter] = useState<[number, number]>(DEFAULT_CENTER);
    const [mapReady, setMapReady] = useState(false);
    const [showDesktopMap, setShowDesktopMap] = useState(false);
    const [isMobileFiltersExpanded, setIsMobileFiltersExpanded] = useState(false);
    const [nearbyData, setNearbyData] = useState<NearbyData | null>(null);
    const [sortBy, setSortBy] = useState<SortOption>('distance_asc');
    const [activeTab, setActiveTab] = useState<ListingTypeFilter>('sale');
    const [currentPage, setCurrentPage] = useState(0);
    const [autoFetchTrigger, setAutoFetchTrigger] = useState(1);
    const [isSearching, setIsSearching] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [isLoadingMore, setIsLoadingMore] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const searchTimeoutRef = useRef<NodeJS.Timeout | null>(null);
    const listScrollRef = useRef<HTMLDivElement | null>(null);
    const loadMoreRef = useRef<HTMLDivElement | null>(null);

    const blurActiveElement = useCallback(() => {
        if (typeof document === 'undefined') return;

        const activeElement = document.activeElement;
        if (activeElement instanceof HTMLElement) {
            activeElement.blur();
        }
    }, []);

    const resetResultsViewport = useCallback(() => {
        listScrollRef.current?.scrollTo({ top: 0, behavior: 'auto' });

        if (typeof window === 'undefined' || !listScrollRef.current) return;

        if (!window.matchMedia('(min-width: 1024px)').matches) {
            const nextTop =
                window.scrollY +
                listScrollRef.current.getBoundingClientRect().top -
                16;
            window.scrollTo({ top: Math.max(0, nextTop), behavior: 'auto' });
        }
    }, []);

    useEffect(() => {
        if (typeof window === 'undefined') return;
        import('leaflet').then((L) => {
            delete (L.Icon.Default.prototype as { _getIconUrl?: string })._getIconUrl;
            L.Icon.Default.mergeOptions({
                iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
                iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
                shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
            });
            setMapReady(true);
        });
    }, []);

    useEffect(() => {
        if (typeof window === 'undefined') return;

        const mediaQuery = window.matchMedia('(min-width: 1024px)');
        const syncDesktopMap = () => setShowDesktopMap(mediaQuery.matches);

        syncDesktopMap();

        if (typeof mediaQuery.addEventListener === 'function') {
            mediaQuery.addEventListener('change', syncDesktopMap);
            return () =>
                mediaQuery.removeEventListener('change', syncDesktopMap);
        }

        mediaQuery.addListener(syncDesktopMap);
        return () => mediaQuery.removeListener(syncDesktopMap);
    }, []);

    useEffect(() => {
        if (!externalLocation) return;
        setSelectedLocation({ lat: externalLocation.lat, lng: externalLocation.lng });
        setSelectedLocationName(externalLocation.name);
        setSearchQuery(externalLocation.name);
        setMapCenter([externalLocation.lat, externalLocation.lng]);
        setNearbyData(null);
        setCurrentPage(0);
        setError(null);
        setAutoFetchTrigger((value) => value + 1);
    }, [externalLocation]);

    const searchPlaces = useCallback(async (query: string) => {
        if (!query.trim() || query.length < 3) {
            setSearchResults([]);
            return;
        }
        setIsSearching(true);
        try {
            const response = await fetch(`/api/geocode?q=${encodeURIComponent(query)}`);
            if (response.ok) setSearchResults(await response.json());
        } catch (err) {
            console.error('Search error:', err);
        } finally {
            setIsSearching(false);
        }
    }, []);

    const handleSearchInput = useCallback((value: string) => {
        setSearchQuery(value);
        if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);
        searchTimeoutRef.current = setTimeout(() => searchPlaces(value), 250);
    }, [searchPlaces]);

    const selectSearchResult = useCallback((result: SearchResult) => {
        const lat = parseFloat(result.lat);
        const lng = parseFloat(result.lon);
        const shortName = result.display_name.split(',')[0];
        blurActiveElement();
        setSelectedLocation({ lat, lng });
        setSelectedLocationName(shortName);
        setSearchQuery(shortName);
        setSearchResults([]);
        setMapCenter([lat, lng]);
        setNearbyData(null);
        setCurrentPage(0);
        setError(null);
        setAutoFetchTrigger((value) => value + 1);
    }, [blurActiveElement]);

    const fetchNearbyListings = useCallback(async ({
        page = 0,
        append = false,
        listingType = activeTab,
        sort = sortBy,
        scrollToResults = true,
    }: FetchOptions = {}) => {
        if (!selectedLocation) return;
        if (append) {
            setIsLoadingMore(true);
        } else {
            if (scrollToResults) resetResultsViewport();
            else listScrollRef.current?.scrollTo({ top: 0, behavior: 'auto' });
            setIsLoading(true);
            setNearbyData(null);
        }
        setError(null);
        try {
            const offset = page * PAGE_SIZE;
            const response = await fetch(`/api/nearby-listings?lat=${selectedLocation.lat}&lng=${selectedLocation.lng}&radius=${radius}&sort_by=${sort}&limit=${PAGE_SIZE}&offset=${offset}&listing_type=${listingType}`);
            if (!response.ok) throw new Error('Error al obtener inmuebles');
            const data: NearbyData = await response.json();
            setNearbyData((current) => (!append || !current ? data : { ...data, listings: mergeListings(current.listings, data.listings) }));
            setCurrentPage(page);
        } catch (err) {
            console.error('Fetch error:', err);
            setError('No se pudieron cargar los inmuebles cercanos.');
        } finally {
            setIsLoading(false);
            setIsLoadingMore(false);
        }
    }, [selectedLocation, radius, sortBy, activeTab, resetResultsViewport]);

    useEffect(() => {
        if (selectedLocation && autoFetchTrigger > 0) {
            fetchNearbyListings({ page: 0, scrollToResults: false });
        }
    }, [autoFetchTrigger, selectedLocation, fetchNearbyListings]);

    useEffect(() => {
        if (!nearbyData?.pagination.has_more || isLoading || isLoadingMore || !loadMoreRef.current) return;
        const observer = new IntersectionObserver((entries) => {
            if (entries[0]?.isIntersecting) fetchNearbyListings({ page: currentPage + 1, append: true });
        }, {
            root: typeof window !== 'undefined' && window.matchMedia('(min-width: 1024px)').matches ? listScrollRef.current : null,
            rootMargin: '260px 0px',
            threshold: 0.01,
        });
        observer.observe(loadMoreRef.current);
        return () => observer.disconnect();
    }, [nearbyData?.pagination.has_more, isLoading, isLoadingMore, currentPage, fetchNearbyListings]);

    const saleStats = nearbyData?.stats.find((item) => item.listing_type === 'sale');
    const rentStats = nearbyData?.stats.find((item) => item.listing_type === 'rent');
    const activeStats = activeTab === 'sale' ? saleStats : rentStats;
    const totalCount = nearbyData?.pagination.total_count || 0;

    const triggerSearch = useCallback((options?: FetchOptions) => {
        blurActiveElement();
        void fetchNearbyListings({ page: 0, ...options });
    }, [blurActiveElement, fetchNearbyListings]);

    return (
        <>
            <div className="flex flex-col rounded-[28px] border border-slate-200 bg-white/78 shadow-[0_24px_80px_rgba(15,23,42,0.08)] backdrop-blur-sm lg:grid lg:h-[calc(100vh-8rem)] lg:grid-cols-[minmax(0,1.1fr)_minmax(420px,0.9fr)] lg:overflow-hidden">
                <section className="order-2 flex min-h-0 flex-col lg:order-none lg:border-r">
                    <div className="space-y-4 border-b border-slate-200 px-4 py-5 md:px-6">
                        <div>
                            <h1 className="text-3xl font-black tracking-tight text-slate-900 md:text-[2.2rem]">
                                {headingFor(activeTab, selectedLocationName)}
                            </h1>
                            <p className="mt-2 text-base text-slate-600">
                                {totalCount > 0
                                    ? `${totalCount.toLocaleString('en-US')} inmuebles encontrados en un radio de ${radius} km.`
                                    : `Explora inmuebles cercanos en un radio de ${radius} km.`}
                            </p>
                        </div>
                    </div>

                    <div ref={listScrollRef} className="px-4 pb-8 pt-4 md:px-6 lg:min-h-0 lg:flex-1 lg:overflow-y-auto">
                        {error ? <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div> : null}

                        {!error && isLoading ? (
                            <div className="grid gap-5 md:grid-cols-2 2xl:grid-cols-3">
                                {Array.from({ length: 6 }).map((_, index) => <div key={index} className="overflow-hidden rounded-[24px] border border-slate-200 bg-white shadow-sm"><div className="aspect-[1.08/1] skeleton-pulse" /><div className="space-y-3 p-4"><div className="skeleton-pulse h-6 w-3/4 rounded-lg" /><div className="skeleton-pulse h-4 w-1/3 rounded-lg" /><div className="skeleton-pulse h-4 w-2/3 rounded-lg" /></div></div>)}
                            </div>
                        ) : null}

                        {!error && !isLoading && nearbyData?.listings.length ? (
                            <div className="grid gap-5 md:grid-cols-2 2xl:grid-cols-3">
                                {nearbyData.listings.map((listing) => (
                                    <div
                                        key={String(listing.external_id)}
                                        className="space-y-2"
                                    >
                                        <ListingCard
                                            listing={toListingCardData(
                                                listing,
                                                selectedLocationName
                                            )}
                                            onClick={() =>
                                                setSelectedListingId(
                                                    listing.external_id
                                                )
                                            }
                                        />
                                        {/* legacy explorer footer removed
                                            <div className="px-1 text-sm font-medium text-slate-500">
                                            {parseFloat(listing.distance_km).toFixed(parseFloat(listing.distance_km) < 10 ? 1 : 0)} km
                                                {[listing.specs?.area_m2 ? `${Number(listing.specs.area_m2).toLocaleString('en-US')} m²` : null, listing.specs?.bedrooms !== undefined && listing.specs?.bedrooms !== null ? `${listing.specs.bedrooms} hab` : null, listing.specs?.bathrooms !== undefined && listing.specs?.bathrooms !== null ? `${listing.specs.bathrooms} baños` : null, listing.specs?.parking !== undefined && listing.specs?.parking !== null ? `${listing.specs.parking} parqueos` : null].filter(Boolean).join(' · ')}
                                            </div>
                                        */}
                                        <div className="px-1 text-sm font-medium text-slate-500">
                                            {parseFloat(
                                                listing.distance_km
                                            ).toFixed(
                                                parseFloat(listing.distance_km) <
                                                    10
                                                    ? 1
                                                    : 0
                                            )}{' '}
                                            km
                                        </div>
                                    </div>
                                ))}
                            </div>
                        ) : null}

                        {!error && !isLoading && nearbyData && nearbyData.listings.length === 0 ? <div className="rounded-[24px] border border-dashed border-slate-300 bg-slate-50 px-6 py-14 text-center"><h2 className="text-xl font-bold text-slate-900">No encontramos resultados en esta zona</h2><p className="mt-2 text-slate-600">Prueba ampliar el radio o mover el punto de búsqueda en el mapa.</p></div> : null}
                        {!error && !isLoading && !nearbyData ? <div className="rounded-[24px] border border-dashed border-slate-300 bg-slate-50 px-6 py-14 text-center"><h2 className="text-xl font-bold text-slate-900">Selecciona una zona para empezar</h2><p className="mt-2 text-slate-600">Busca un lugar o toca el mapa, luego usa “Buscar en esta zona” para cargar inmuebles cercanos.</p></div> : null}
                        <div ref={loadMoreRef} className="h-1" />
                        {isLoadingMore ? <div className="flex items-center justify-center py-6"><div className="h-8 w-8 animate-spin rounded-full border-4 border-[var(--primary)] border-t-transparent" /></div> : null}
                    </div>
                </section>

                <aside className="order-1 flex flex-col border-b border-slate-200 lg:order-none lg:min-h-0 lg:border-b-0">
                    <div className="sticky top-14 z-30 border-b border-slate-200 bg-white/95 px-4 py-4 backdrop-blur-sm md:px-5 lg:hidden">
                        <SearchControls
                            searchQuery={searchQuery}
                            isSearching={isSearching}
                            searchResults={searchResults}
                            isLoading={isLoading}
                            disabled={!selectedLocation}
                            variant="mobile"
                            onInputChange={handleSearchInput}
                            onSelectResult={selectSearchResult}
                            onSearch={() => triggerSearch({ scrollToResults: false })}
                        />
                    </div>

                    <div className="relative hidden lg:block lg:h-[48vh] lg:min-h-0 lg:flex-1">
                        {showDesktopMap && mapReady ? (
                            <MapContainer center={mapCenter} zoom={DEFAULT_ZOOM} style={{ height: '100%', width: '100%' }} scrollWheelZoom={true}>
                                <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                                <MapClickHandler onMapClick={(lat, lng) => {
                                    setSelectedLocation({ lat, lng });
                                    setSelectedLocationName('Zona seleccionada');
                                    setMapCenter([lat, lng]);
                                    setNearbyData(null);
                                    setCurrentPage(0);
                                    setError(null);
                                }} />
                                <MapCenterUpdater center={mapCenter} />
                                {selectedLocation ? <>
                                    <Marker position={[selectedLocation.lat, selectedLocation.lng]} />
                                    <Circle center={[selectedLocation.lat, selectedLocation.lng]} radius={radius * 1000} pathOptions={{ color: '#2563eb', fillColor: '#60a5fa', fillOpacity: 0.16, weight: 2 }} />
                                </> : null}
                            </MapContainer>
                        ) : showDesktopMap ? <div className="h-full w-full skeleton-pulse" /> : null}

                        <div className="pointer-events-none absolute inset-x-0 top-0 z-[500] p-3 md:p-4">
                            <div className="ml-14 md:ml-16">
                                <SearchControls
                                    searchQuery={searchQuery}
                                    isSearching={isSearching}
                                    searchResults={searchResults}
                                    isLoading={isLoading}
                                    disabled={!selectedLocation}
                                    variant="desktop"
                                    onInputChange={handleSearchInput}
                                    onSelectResult={selectSearchResult}
                                    onSearch={() => triggerSearch()}
                                />
                            </div>
                        </div>

                        {false && (
                            <div className="pointer-events-none absolute inset-x-0 bottom-0 z-[500] p-4 md:p-5">
                            <div className="pointer-events-auto rounded-2xl border border-white/50 bg-white/95 p-4 shadow-xl backdrop-blur-sm">
                                <div className="mb-3 flex items-center justify-between gap-4">
                                    <div><p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Radio de búsqueda</p><p className="mt-1 text-lg font-bold text-slate-900">{radius} km</p></div>
                                    <p className="max-w-[180px] text-right text-xs text-slate-500">Toca el mapa para mover el punto de búsqueda.</p>
                                </div>
                                <input type="range" min="0.5" max="10" step="0.5" value={radius} onChange={(event) => setRadius(parseFloat(event.target.value))} className="h-2 w-full accent-[var(--primary)]" aria-label="Radio de búsqueda" />
                            </div>
                        </div>
                        )}
                    </div>

                    <div className="bg-white/92 px-4 py-2.5 md:px-5 lg:border-t lg:border-slate-200 lg:px-6">
                        <button
                            type="button"
                            onClick={() =>
                                setIsMobileFiltersExpanded((current) => !current)
                            }
                            aria-expanded={isMobileFiltersExpanded}
                            aria-controls="mobile-explorer-filters"
                            className="flex w-full items-center justify-between rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-left shadow-sm transition hover:border-slate-300 lg:hidden"
                        >
                            <div className="min-w-0">
                                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                                    Filtros y resumen
                                </p>
                                <p className="mt-1 truncate text-sm font-semibold text-slate-900">
                                    {radius} km | {selectedLocationName}
                                </p>
                            </div>
                            <svg
                                className={`h-5 w-5 flex-shrink-0 text-slate-500 transition-transform ${
                                    isMobileFiltersExpanded ? 'rotate-180' : ''
                                }`}
                                viewBox="0 0 20 20"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="1.8"
                                aria-hidden="true"
                            >
                                <path
                                    d="m5 7.5 5 5 5-5"
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                />
                            </svg>
                        </button>

                        <div
                            id="mobile-explorer-filters"
                            className={`mt-2.5 space-y-2.5 lg:mt-0 ${
                                isMobileFiltersExpanded ? 'block' : 'hidden'
                            } lg:block`}
                        >
                            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2.5">
                                <div className="mb-2 flex items-center justify-between gap-3">
                                    <div>
                                        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                                            Radio de búsqueda
                                        </p>
                                        <p className="mt-0.5 text-[1.3rem] font-black leading-none text-slate-900">
                                            {radius} km
                                        </p>
                                    </div>
                                    <p className="max-w-[165px] text-right text-[10px] leading-snug text-slate-500">
                                        Toca el mapa para mover el punto de
                                        búsqueda.
                                    </p>
                                </div>
                                <input
                                    type="range"
                                    min="0.5"
                                    max="10"
                                    step="0.5"
                                    value={radius}
                                    onChange={(event) =>
                                        setRadius(parseFloat(event.target.value))
                                    }
                                    className="h-1.5 w-full accent-[var(--primary)]"
                                    aria-label="Radio de búsqueda"
                                />
                            </div>

                            <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                                <div className="inline-flex w-fit rounded-2xl bg-slate-100 p-1">
                                    {(['sale', 'rent'] as ListingTypeFilter[]).map((tab) => (
                                        <button
                                            key={tab}
                                            onClick={() => {
                                                setActiveTab(tab);
                                                setCurrentPage(0);
                                                void fetchNearbyListings({ page: 0, listingType: tab });
                                            }}
                                            className={`rounded-[14px] px-3 py-1.5 text-[12px] font-semibold transition-all ${activeTab === tab ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900'}`}
                                        >
                                            {tab === 'sale' ? 'Venta' : 'Renta'}
                                        </button>
                                    ))}
                                </div>

                                <div className="flex items-center gap-2">
                                    <label htmlFor="explorer-sort" className="text-[12px] font-medium text-slate-500">Ordenar:</label>
                                    <select
                                        id="explorer-sort"
                                        value={sortBy}
                                        onChange={(event) => {
                                            const nextSort = event.target.value as SortOption;
                                            setSortBy(nextSort);
                                            setCurrentPage(0);
                                            void fetchNearbyListings({ page: 0, sort: nextSort });
                                        }}
                                        className="rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-[12px] font-medium text-slate-700 shadow-sm outline-none focus:border-[var(--primary)] focus:ring-2 focus:ring-[var(--primary)]/15"
                                    >
                                        {SORT_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                                    </select>
                                </div>
                            </div>

                            <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
                                <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2.5">
                                    <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Precio medio</p>
                                    <p className="mt-1 text-[1rem] font-black text-slate-900 sm:text-[1.2rem]">{activeStats ? formatPrice(activeStats.median_price) : 'Sin datos'}</p>
                                </div>
                                <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2.5">
                                    <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Rango</p>
                                    <p className="mt-1 text-[0.95rem] font-bold text-slate-900 sm:text-base">{activeStats ? `${formatPriceShort(activeStats.min_price)} - ${formatPriceShort(activeStats.max_price)}` : 'Sin datos'}</p>
                                </div>
                                <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2.5 sm:col-span-2 xl:col-span-1">
                                    <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Ubicación activa</p>
                                    <p className="mt-1 text-[0.95rem] font-bold text-slate-900 sm:text-base">{selectedLocationName}</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </aside>
            </div>

            {selectedListingId !== null ? <ListingModal externalId={selectedListingId} onClose={() => setSelectedListingId(null)} /> : null}
        </>
    );
}
