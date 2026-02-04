'use client';

import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import Navbar from '@/components/Navbar';
import ListingCard from '@/components/ListingCard';
import ListingModal from '@/components/ListingModal';
import BestOpportunitySection from '@/components/BestOpportunitySection';
import TagFilterChips from '@/components/TagFilterChips';
import { slugToDepartamento } from '@/lib/slugify';

// Lean listing shape from new API
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
    tags: string[] | null;  // For client-side filtering
    total_count: number;
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

type FilterType = 'all' | 'sale' | 'rent';
type SortOption = 'recent' | 'price_asc' | 'price_desc';

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

    const [listings, setListings] = useState<CardListing[]>([]);
    const [sortBy, setSortBy] = useState<SortOption>('price_asc');
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

    // Client-side tag filtering
    const [selectedFilterTags, setSelectedFilterTags] = useState<string[]>([]);
    // Store initial tags from first load to prevent counts from changing
    const [initialListingTags, setInitialListingTags] = useState<(string[] | null)[]>([]);

    // Fetch listings with pagination
    const fetchListings = useCallback(async (offset: number, type: FilterType, sort: SortOption, append: boolean = false) => {
        const typeParam = type === 'all' ? '' : `&type=${type}`;
        const res = await fetch(`/api/department/${slug}?limit=${PAGE_SIZE}&offset=${offset}${typeParam}&sort=${sort}`);

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
        return data;
    }, [slug]);

    // Initial load - refetch when filter changes (via URL)
    useEffect(() => {
        async function fetchData() {
            setIsLoading(true);
            setError(null);
            setListings([]); // Clear listings when filter changes
            setSelectedFilterTags([]); // Reset filters on new load
            try {
                // Fetch listings and best opportunities in parallel
                const [listingsData, topScoredRes] = await Promise.all([
                    fetchListings(0, filter, sortBy),
                    fetch(`/api/department/${slug}/top-scored?type=all&limit=1`)
                ]);

                // Store initial tags for stable tag chip counts
                if (listingsData?.listings) {
                    setInitialListingTags(listingsData.listings.map((l: CardListing) => l.tags));
                }

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
    }, [slug, fetchListings, filter, sortBy]);

    // Load more handler
    const handleLoadMore = useCallback(async () => {
        if (isLoadingMore || !pagination.hasMore) return;

        setIsLoadingMore(true);
        try {
            const newOffset = pagination.offset + PAGE_SIZE;
            await fetchListings(newOffset, filter, sortBy, true);
        } catch (err) {
            console.error('Error loading more:', err);
        } finally {
            setIsLoadingMore(false);
        }
    }, [isLoadingMore, pagination.hasMore, pagination.offset, filter, sortBy, fetchListings]);

    // Intersection Observer for infinite scroll
    // Disabled when filter tags are selected
    useEffect(() => {
        const element = loadMoreRef.current;
        if (!element) return;
        // Don't observe when filters are active
        if (selectedFilterTags.length > 0) return;

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
    }, [handleLoadMore, pagination.hasMore, isLoadingMore, isLoading, selectedFilterTags.length]);

    // Filter listings based on selected filter tags (client-side)
    const filteredListings = useMemo(() => {
        if (selectedFilterTags.length === 0) return listings;
        return listings.filter(l =>
            selectedFilterTags.some(tag => l.tags?.includes(tag))
        );
    }, [listings, selectedFilterTags]);

    // Convert CardListing to format expected by ListingCard
    const listingsForCard = useMemo(() => {
        return filteredListings.map(l => {
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
                location: l.municipio ? { municipio_detectado: l.municipio } : null
            };
        });
    }, [filteredListings]);

    // Handle view listing from best opportunity
    const handleViewBestListing = (topScored: TopScoredListing) => {
        // Open URL directly since we don't have full listing data
        window.open(topScored.url, '_blank');
    };

    // Determine which best opportunities to show based on filter
    const showBestSale = filter === 'all' || filter === 'sale';
    const showBestRent = filter === 'all' || filter === 'rent';

    const featuredIds = useMemo(() => {
        const ids = new Set<string>();
        if (bestSale?.external_id !== undefined && bestSale?.external_id !== null) ids.add(String(bestSale.external_id));
        if (bestRent?.external_id !== undefined && bestRent?.external_id !== null) ids.add(String(bestRent.external_id));
        return ids;
    }, [bestSale?.external_id, bestRent?.external_id]);

    const clearTagFilters = useCallback(() => setSelectedFilterTags([]), []);

    const resultsCount = selectedFilterTags.length > 0 ? filteredListings.length : pagination.total;

    const appliedSummary = useMemo(() => {
        const parts: string[] = [];
        if (filter === 'sale') parts.push('Venta');
        if (filter === 'rent') parts.push('Renta');

        if (selectedFilterTags.length > 0) {
            parts.push(...selectedFilterTags.map(t => t));
        }

        return parts;
    }, [filter, selectedFilterTags]);

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
                        <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 16 16">
                            <path fillRule="evenodd" d="M15 8a.5.5 0 0 0-.5-.5H2.707l3.147-3.146a.5.5 0 1 0-.708-.708l-4 4a.5.5 0 0 0 0 .708l4 4a.5.5 0 0 0 .708-.708L2.707 8.5H14.5A.5.5 0 0 0 15 8z" />
                        </svg>
                        Volver al índice
                    </Link>

                    <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
                        <div>
                            <h1 className="text-4xl md:text-5xl font-black text-[var(--text-primary)] tracking-tight">
                                {departamento}
                            </h1>
                            <p className="status-line">
                                {isLoading ? (
                                    <span>Cargando…</span>
                                ) : (
                                    <>
                                        <span>{pagination.total}</span> propiedades{getFilterDisplayText(filter) ? ` ${getFilterDisplayText(filter)}` : ''} · <span>Mostrando {listings.length}</span>
                                    </>
                                )}
                            </p>
                        </div>

                        <div className="flex flex-wrap items-center gap-4">
                            <div className="pill-group">
                                <Link
                                    href={`/${slug}`}
                                    className={`pill-btn ${filter === 'all' ? 'active' : ''}`}
                                >
                                    Todos
                                </Link>
                                <Link
                                    href={`/${slug}/venta`}
                                    className={`pill-btn ${filter === 'sale' ? 'active' : ''}`}
                                >
                                    Venta
                                </Link>
                                <Link
                                    href={`/${slug}/renta`}
                                    className={`pill-btn ${filter === 'rent' ? 'active' : ''}`}
                                >
                                    Renta
                                </Link>
                            </div>

                            <div className="dropdown-control">
                                <select
                                    value={sortBy}
                                    onChange={(e) => setSortBy(e.target.value as SortOption)}
                                    className="dropdown-select"
                                >
                                    <option value="price_asc">Precio: menor a mayor</option>
                                    <option value="price_desc">Precio: mayor a menor</option>
                                    <option value="recent">Más recientes</option>
                                </select>
                                <div className="dropdown-icon" aria-hidden="true">
                                    <svg width="16" height="16" viewBox="0 0 20 20" fill="none">
                                        <path d="M6 8l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                                    </svg>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Content */}
                {isLoading ? (
                    <div className="flex flex-col justify-center items-center min-h-[400px] gap-4">
                        <div className="spinner"></div>
                        <p className="text-[var(--text-secondary)]">Cargando propiedades...</p>
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

                        <div className="card-float border-l-4 border-l-[var(--primary)] bg-gradient-to-r from-[var(--primary-light)] to-white p-4 md:p-5 mb-8">
                            <div className="flex flex-wrap items-center justify-between gap-3 mb-4 pb-3 border-b border-slate-100">
                                <div className="flex items-center gap-2">
                                    <svg className="w-4 h-4 text-[var(--primary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
                                    </svg>
                                    <h2 className="text-xs font-black uppercase tracking-widest text-[var(--text-primary)]">Filtros</h2>
                                </div>
                                <div className="flex items-center gap-4">
                                    <span className="text-xs text-[var(--text-muted)]">
                                        Resultados: <span className="font-bold text-[var(--text-secondary)]">{resultsCount}</span>
                                    </span>
                                    <button
                                        type="button"
                                        onClick={clearTagFilters}
                                        disabled={selectedFilterTags.length === 0}
                                        className="text-xs font-semibold text-[var(--primary)] hover:text-[var(--primary-hover)] transition-colors disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1"
                                    >
                                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                                        </svg>
                                        Limpiar filtros
                                    </button>
                                </div>
                            </div>

                            {initialListingTags.length > 0 && (
                                <TagFilterChips
                                    variant="department"
                                    allListingTags={initialListingTags}
                                    primaryTag={departamento}
                                    selectedTags={selectedFilterTags}
                                    maxVisible={10}
                                    onToggleTag={(tag) => {
                                        setSelectedFilterTags(prev =>
                                            prev.includes(tag)
                                                ? prev.filter(t => t !== tag)
                                                : [...prev, tag]
                                        );
                                    }}
                                />
                            )}
                        </div>

                        <div className="mb-8">
                            <div className="mb-5 pb-3 border-b-2 border-slate-100">
                                <div className="flex items-center gap-2 mb-2">
                                    <svg className="w-4 h-4 text-[var(--text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
                                    </svg>
                                    <div className="text-xs font-black uppercase tracking-widest text-[var(--text-primary)]">Todas las propiedades</div>
                                </div>
                                {appliedSummary.length > 0 ? (
                                    <div className="text-sm text-[var(--text-muted)]">
                                        Aplicando: <span className="font-medium text-[var(--text-secondary)]">{appliedSummary.join(' · ')}</span>
                                    </div>
                                ) : (
                                    <div className="text-sm text-[var(--text-muted)]">
                                        Explorá el catálogo completo de propiedades en {departamento}
                                    </div>
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
                                    No hay propiedades {getFilterDisplayText(filter)} en este departamento.
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
