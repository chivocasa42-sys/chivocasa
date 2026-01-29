'use client';

import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import Navbar from '@/components/Navbar';
import ListingCard from '@/components/ListingCard';
import ListingModal from '@/components/ListingModal';
import BestOpportunitySection from '@/components/BestOpportunitySection';
import { slugToDepartamento } from '@/lib/slugify';

// Lean listing shape from new API
interface CardListing {
    external_id: number;
    title: string;
    price: number;
    listing_type: 'sale' | 'rent';
    first_image: string | null;
    bedrooms: number | null;
    bathrooms: number | null;
    area: number | null;
    municipio: string | null;
    total_count: number;
}

interface TopScoredListing {
    external_id: number;
    title: string;
    price: number;
    mt2: number;
    bedrooms: number;
    bathrooms: number;
    price_per_m2: number;
    score: number;
    url: string;
}

interface PaginationState {
    total: number;
    limit: number;
    offset: number;
    hasMore: boolean;
}

type FilterType = 'all' | 'sale' | 'rent';

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

    // Fetch listings with pagination
    const fetchListings = useCallback(async (offset: number, type: FilterType, append: boolean = false) => {
        const typeParam = type === 'all' ? '' : `&type=${type}`;
        const res = await fetch(`/api/department/${slug}?limit=${PAGE_SIZE}&offset=${offset}${typeParam}`);

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
            try {
                // Fetch listings and best opportunities in parallel
                const [, topScoredRes] = await Promise.all([
                    fetchListings(0, filter),
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
    }, [slug, fetchListings, filter]);

    // Load more handler
    const handleLoadMore = useCallback(async () => {
        if (isLoadingMore || !pagination.hasMore) return;

        setIsLoadingMore(true);
        try {
            const newOffset = pagination.offset + PAGE_SIZE;
            await fetchListings(newOffset, filter, true);
        } catch (err) {
            console.error('Error loading more:', err);
        } finally {
            setIsLoadingMore(false);
        }
    }, [isLoadingMore, pagination.hasMore, pagination.offset, filter, fetchListings]);

    // Intersection Observer for infinite scroll
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
                location: l.municipio ? { municipio_detectado: l.municipio } : null
            };
        });
    }, [listings]);

    // Handle view listing from best opportunity
    const handleViewBestListing = (topScored: TopScoredListing) => {
        // Open URL directly since we don't have full listing data
        window.open(topScored.url, '_blank');
    };

    // Determine which best opportunities to show based on filter
    const showBestSale = filter === 'all' || filter === 'sale';
    const showBestRent = filter === 'all' || filter === 'rent';

    return (
        <>
            <Navbar
                totalListings={pagination.total}
                onRefresh={() => window.location.reload()}
            />

            <main className="container mx-auto px-4 max-w-7xl">
                {/* Back link */}
                <Link
                    href="/"
                    className="inline-flex items-center gap-2 text-[var(--primary)] hover:text-[var(--primary-hover)] mb-6 font-medium transition-colors"
                >
                    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 16 16">
                        <path fillRule="evenodd" d="M15 8a.5.5 0 0 0-.5-.5H2.707l3.147-3.146a.5.5 0 1 0-.708-.708l-4 4a.5.5 0 0 0 0 .708l4 4a.5.5 0 0 0 .708-.708L2.707 8.5H14.5A.5.5 0 0 0 15 8z" />
                    </svg>
                    Volver al Índice
                </Link>

                {/* Header */}
                <div className="flex flex-wrap justify-between items-start gap-4 mb-8">
                    <div>
                        <h1 className="text-3xl font-bold text-[var(--text-primary)]">
                            {departamento}
                        </h1>
                        <p className="text-[var(--text-secondary)] mt-1">
                            {pagination.total} propiedades{getFilterDisplayText(filter) ? ` ${getFilterDisplayText(filter)}` : ''}
                            {listings.length < pagination.total && ` • Mostrando ${listings.length}`}
                        </p>
                    </div>

                    {/* Filter Links - SEO friendly navigation */}
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
                        {/* Best Opportunities - filtered based on URL */}
                        <BestOpportunitySection
                            saleListing={showBestSale ? bestSale : null}
                            rentListing={showBestRent ? bestRent : null}
                            onViewListing={handleViewBestListing}
                        />

                        {/* Listings Grid */}
                        {listingsForCard.length > 0 ? (
                            <>
                                <h2 className="text-lg font-semibold text-[var(--text-primary)] mb-4">
                                    {filter === 'sale' ? 'Propiedades en venta' : filter === 'rent' ? 'Propiedades en renta' : 'Todas las propiedades'}
                                </h2>
                                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
                                    {listingsForCard.map((listing) => (
                                        <ListingCard
                                            key={listing.external_id}
                                            listing={listing}
                                            onClick={() => setSelectedListingId(listing.external_id)}
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
