'use client';

import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import Navbar from '@/components/Navbar';
import ListingCard from '@/components/ListingCard';
import ListingModal from '@/components/ListingModal';
import BestOpportunitySection from '@/components/BestOpportunitySection';
import DepartmentFilterBar from '@/components/DepartmentFilterBar';
import ActiveFilterChips from '@/components/ActiveFilterChips';
import { useDepartmentFilters } from '@/hooks/useDepartmentFilters';
import type { FilterType, SortOption } from '@/hooks/useDepartmentFilters';
import { slugToDepartamento } from '@/lib/slugify';

// Lean listing shape from new API (v2 - location hierarchy)
interface CardListing {
    external_id: string | number;
    title: string;
    price: number;
    listing_type: 'sale' | 'rent';
    first_image: string | null;
    bedrooms: number | null;
    bathrooms: number | null;
    area: number | null;
    municipio: string | null;
    published_date: string | null;
    last_updated: string | null;
    total_count: number;
}

interface Municipality {
    municipio_id: number;
    municipio_name: string;
    listing_count: number;
}

interface TopScoredListing {
    external_id: string | number;
    title: string;
    price: number;
    mt2: number;
    bedrooms: number;
    bathrooms: number;
    price_per_m2: number;
    score: number;
    url: string;
    first_image?: string | null;
}

interface PaginationState {
    total: number;
    limit: number;
    offset: number;
    hasMore: boolean;
}

// FilterType and SortOption imported from useDepartmentFilters

const PAGE_SIZE = 24;

// Map URL tipo to API filter type
function tipoToFilter(tipo: string | undefined): FilterType {
    if (tipo === 'venta') return 'sale';
    if (tipo === 'renta') return 'rent';
    return 'all';
}

// Get display text for current filter
function getFilterDisplayText(filter: FilterType): string {
    if (filter === 'sale') return 'en venta';
    if (filter === 'rent') return 'en renta';
    return '';
}

export default function DepartmentPage() {
    const params = useParams();
    const slug = params.departamento as string;
    const departamento = slugToDepartamento(slug);

    // Get filter from URL path (filter is an array from catch-all, e.g., ['venta'])
    const filterParam = params.filter as string[] | undefined;
    const filterSlug = filterParam?.[0]; // First segment: 'venta' or 'alquiler'
    const filter: FilterType = tipoToFilter(filterSlug);

    // Unified filter state (single source of truth)
    const {
        filters,
        setType,
        setSort,
        applyPrice,
        clearPrice,
        setMunicipio,
        toggleCategory,
        removeChip,
        clearAll,
        activeChips,
        activeFiltersCount,
        hasActiveFilters,
        priceLabel,
    } = useDepartmentFilters({ slug, initialType: filter });

    const [listings, setListings] = useState<CardListing[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isLoadingMore, setIsLoadingMore] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [selectedListingId, setSelectedListingId] = useState<string | number | null>(null);
    const loadMoreRef = useRef<HTMLDivElement>(null);
    const [pagination, setPagination] = useState<PaginationState>({
        total: 0,
        limit: PAGE_SIZE,
        offset: 0,
        hasMore: false
    });

    // Best opportunities - only show relevant ones based on filter
    const [bestSale, setBestSale] = useState<TopScoredListing | null>(null);
    const [bestRent, setBestRent] = useState<TopScoredListing | null>(null);

    // Available municipalities in this department
    const [municipalities, setMunicipalities] = useState<Municipality[]>([]);

    // Fetch listings with pagination and optional filters
    const fetchListings = useCallback(async (
        offset: number,
        type: FilterType,
        sort: SortOption,
        municipio: string | null = null,
        append: boolean = false,
        priceMin: number | null = null,
        priceMax: number | null = null,
    ) => {
        const typeParam = type === 'all' ? '' : `&type=${type}`;
        const municipioParam = municipio ? `&municipio=${encodeURIComponent(municipio)}` : '';
        const priceMinParam = priceMin != null ? `&price_min=${priceMin}` : '';
        const priceMaxParam = priceMax != null ? `&price_max=${priceMax}` : '';
        const res = await fetch(`/api/department/${slug}?limit=${PAGE_SIZE}&offset=${offset}${typeParam}&sort=${sort}${municipioParam}${priceMinParam}${priceMaxParam}`);

        if (!res.ok) {
            if (res.status === 404) {
                throw new Error('Departamento no encontrado');
            }
            throw new Error('Failed to fetch');
        }

        const data = await res.json();

        if (append) {
            setListings(prev => [...prev, ...data.listings]);
        } else {
            setListings(data.listings || []);
        }

        setPagination(data.pagination);

        // Store municipalities from initial load
        if (data.municipalities && data.municipalities.length > 0) {
            setMunicipalities(data.municipalities);
        }

        return data;
    }, [slug]);

    // Initial load - refetch when any filter changes
    useEffect(() => {
        async function fetchData() {
            setIsLoading(true);
            setError(null);
            setListings([]); // Clear listings when filter changes
            try {
                // Fetch listings and best opportunities in parallel
                const [listingsData, topScoredRes] = await Promise.all([
                    fetchListings(0, filters.listingType, filters.sort, filters.municipio, false, filters.priceMin, filters.priceMax),
                    fetch(`/api/department/${slug}/top-scored?type=all&limit=1`)
                ]);

                if (topScoredRes.ok) {
                    const topScoredData = await topScoredRes.json();
                    setBestSale(topScoredData.sale?.[0] || null);
                    setBestRent(topScoredData.rent?.[0] || null);
                }
            } catch (err) {
                setError(err instanceof Error ? err.message : 'No pudimos cargar los datos. Intentá de nuevo.');
                console.error(err);
            } finally {
                setIsLoading(false);
            }
        }

        if (slug) fetchData();
    }, [slug, fetchListings, filters.listingType, filters.sort, filters.municipio, filters.priceMin, filters.priceMax]);

    // Load more handler
    const handleLoadMore = useCallback(async () => {
        if (isLoadingMore || !pagination.hasMore) return;

        setIsLoadingMore(true);
        try {
            const newOffset = pagination.offset + PAGE_SIZE;
            await fetchListings(newOffset, filters.listingType, filters.sort, filters.municipio, true, filters.priceMin, filters.priceMax);
        } catch (err) {
            console.error('Error loading more:', err);
        } finally {
            setIsLoadingMore(false);
        }
    }, [isLoadingMore, pagination.hasMore, pagination.offset, filters, fetchListings]);

    // Intersection Observer for infinite scroll
    // Disabled when filter tags are selected
    useEffect(() => {
        const element = loadMoreRef.current;
        if (!element) return;

        const observer = new IntersectionObserver(
            (entries) => {
                const first = entries[0];
                if (first.isIntersecting && pagination.hasMore && !isLoadingMore && !isLoading) {
                    handleLoadMore();
                }
            },
            { threshold: 0.1, rootMargin: '100px' }
        );

        observer.observe(element);
        return () => observer.disconnect();
    }, [handleLoadMore, pagination.hasMore, isLoadingMore, isLoading]);

    // Convert CardListing to format expected by ListingCard
    const listingsForCard = useMemo(() => {
        return listings.map(l => {
            const specs: Record<string, string | number> = {};
            if (l.bedrooms !== null) specs.bedrooms = l.bedrooms;
            if (l.bathrooms !== null) specs.bathrooms = l.bathrooms;
            if (l.area !== null) specs['Área construida (m²)'] = l.area;

            return {
                external_id: l.external_id,
                title: l.title,
                price: l.price,
                listing_type: l.listing_type,
                images: l.first_image ? [l.first_image] : null,
                specs: Object.keys(specs).length > 0 ? specs : null,
                location: l.municipio ? { municipio_detectado: l.municipio } : null,
                published_date: l.published_date || l.last_updated || undefined
            };
        });
    }, [listings]);

    // Handle view listing from best opportunity - open in modal
    const handleViewBestListing = (topScored: TopScoredListing) => {
        setSelectedListingId(topScored.external_id);
    };

    // Determine which best opportunities to show based on filter
    const showBestSale = filters.listingType === 'all' || filters.listingType === 'sale';
    const showBestRent = filters.listingType === 'all' || filters.listingType === 'rent';

    const featuredIds = useMemo(() => {
        const ids = new Set<string>();
        if (bestSale?.external_id !== undefined && bestSale?.external_id !== null) ids.add(String(bestSale.external_id));
        if (bestRent?.external_id !== undefined && bestRent?.external_id !== null) ids.add(String(bestRent.external_id));
        return ids;
    }, [bestSale?.external_id, bestRent?.external_id]);

    const resultsCount = pagination.total;

    return (
        <>
            <Navbar
                totalListings={pagination.total}
                onRefresh={() => window.location.reload()}
            />

            <main className="container mx-auto px-4 max-w-7xl">
                <div className="mb-8">
                    <Link
                        href="/"
                        className="inline-flex items-center gap-2 text-[var(--primary)] hover:text-[var(--primary-hover)] mb-5 font-medium transition-colors"
                    >
                        <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 16 16" aria-hidden="true">
                            <path fillRule="evenodd" d="M15 8a.5.5 0 0 0-.5-.5H2.707l3.147-3.146a.5.5 0 1 0-.708-.708l-4 4a.5.5 0 0 0 0 .708l4 4a.5.5 0 0 0 .708-.708L2.707 8.5H14.5A.5.5 0 0 0 15 8z" />
                        </svg>
                        Volver al índice
                    </Link>

                    <div>
                        <h1 className="text-4xl md:text-5xl font-black text-[var(--text-primary)] tracking-tight">
                            {departamento}
                        </h1>
                        <p className="status-line">
                            {isLoading ? (
                                <span>Cargando…</span>
                            ) : (
                                <>
                                    <span>{pagination.total}</span> propiedades{getFilterDisplayText(filters.listingType) ? ` ${getFilterDisplayText(filters.listingType)}` : ''} · <span>Mostrando {listings.length}</span>
                                </>
                            )}
                        </p>
                    </div>
                </div>

                {/* Unified Filter Bar */}
                <DepartmentFilterBar
                    listingType={filters.listingType}
                    sort={filters.sort}
                    priceLabel={priceLabel}
                    priceMin={filters.priceMin}
                    priceMax={filters.priceMax}
                    activeFiltersCount={activeFiltersCount}
                    hasActiveFilters={hasActiveFilters}
                    resultsCount={resultsCount}
                    municipalities={municipalities}
                    selectedMunicipio={filters.municipio}
                    categories={filters.categories}
                    onTypeChange={setType}
                    onSortChange={setSort}
                    onPriceApply={applyPrice}
                    onPriceClear={clearPrice}
                    onMunicipioSelect={setMunicipio}
                    onCategoryToggle={toggleCategory}
                    onClearAll={clearAll}
                />

                {/* Active Filter Chips */}
                <ActiveFilterChips
                    chips={activeChips}
                    onRemove={removeChip}
                />

                {/* Content */}
                {isLoading ? (
                    <div className="mb-8">
                        {/* Skeleton: Best Opportunity */}
                        <div className="skeleton-pulse skeleton-opportunity" />

                        {/* Skeleton: Filter bar */}
                        <div className="skeleton-pulse skeleton-filter-bar" />

                        {/* Skeleton: Section header */}
                        <div className="text-center mb-6 pb-4 border-b border-slate-200">
                            <div className="skeleton-pulse mx-auto mb-2" style={{ height: 32, width: 260 }} />
                            <div className="skeleton-pulse mx-auto" style={{ height: 18, width: 320 }} />
                        </div>

                        {/* Skeleton: Listing cards grid */}
                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
                            {Array.from({ length: 8 }).map((_, i) => (
                                <div key={i} className="skeleton-card">
                                    <div className="skeleton-pulse skeleton-card__image" />
                                    <div className="skeleton-card__body">
                                        <div className="skeleton-pulse skeleton-card__price" />
                                        <div className="skeleton-pulse skeleton-card__specs" />
                                        <div className="skeleton-card__tags">
                                            <div className="skeleton-pulse skeleton-card__tag" />
                                            <div className="skeleton-pulse skeleton-card__tag" />
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                ) : error ? (
                    <div className="card-float p-8 text-center">
                        <p className="text-[var(--text-secondary)] mb-4">{error}</p>
                        <Link href="/" className="btn-primary">
                            Volver al Índice
                        </Link>
                    </div>
                ) : (
                    <>
                        <BestOpportunitySection
                            saleListing={showBestSale ? bestSale : null}
                            rentListing={showBestRent ? bestRent : null}
                            onViewListing={handleViewBestListing}
                            departamentoName={departamento}
                        />

                        <div className="mb-8">
                            <div className="text-center mb-6 pb-4 border-b border-slate-200">
                                <h2 className="text-2xl md:text-3xl font-black text-[var(--text-primary)] tracking-tight mb-2">
                                    Todas las propiedades
                                </h2>
                                {hasActiveFilters ? (
                                    <p className="text-base text-[var(--text-muted)]">
                                        Aplicando: <span className="font-semibold text-[var(--text-secondary)]">{activeChips.map(c => c.label).join(' · ')}</span>
                                    </p>
                                ) : (
                                    <p className="text-base text-[var(--text-muted)]">
                                        Explorá el catálogo completo de propiedades en <span className="font-semibold text-[var(--text-secondary)]">{departamento}</span>
                                    </p>
                                )}
                            </div>

                            {listingsForCard.length > 0 ? (
                                <>
                                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
                                        {listingsForCard.map((listing) => (
                                            <ListingCard
                                                key={listing.external_id}
                                                listing={listing}
                                                onClick={() => setSelectedListingId(listing.external_id)}
                                                isFeatured={featuredIds.has(String(listing.external_id))}
                                            />
                                        ))}
                                    </div>

                                    {/* Infinite Scroll Trigger */}
                                    {pagination.hasMore && (
                                        <div
                                            ref={loadMoreRef}
                                            className="flex justify-center items-center py-8"
                                        >
                                            {isLoadingMore && (
                                                <div className="flex items-center gap-3 text-[var(--text-secondary)]">
                                                    <div className="spinner"></div>
                                                    <span>Cargando más propiedades...</span>
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </>
                            ) : (
                                <div className="card-float p-8 text-center">
                                    <p className="text-[var(--text-secondary)]">
                                        No hay propiedades {getFilterDisplayText(filters.listingType)} en este departamento.
                                    </p>
                                </div>
                            )}
                        </div>
                    </>
                )}
            </main>

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
