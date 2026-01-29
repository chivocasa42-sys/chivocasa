'use client';

import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import Navbar from '@/components/Navbar';
import ListingCard from '@/components/ListingCard';
import ListingModal from '@/components/ListingModal';
import BestOpportunitySection from '@/components/BestOpportunitySection';

// Lean listing shape from API
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
type SortOption = 'recent' | 'price_asc' | 'price_desc';

const PAGE_SIZE = 24;

// Map URL filter to API filter type
function filterToType(filter: string | undefined): FilterType {
    if (filter === 'venta') return 'sale';
    if (filter === 'alquiler') return 'rent';
    return 'all';
}

export default function TagPage() {
    const params = useParams();
    const slug = params.tag as string;

    // Get filter from URL path
    const filterParam = params.filter as string[] | undefined;
    const filterSlug = filterParam?.[0];
    const filter: FilterType = filterToType(filterSlug);





    const [tagName, setTagName] = useState<string>('');
    const [sortBy, setSortBy] = useState<SortOption>('price_asc');
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

    // Best opportunities
    const [bestSale, setBestSale] = useState<TopScoredListing | null>(null);
    const [bestRent, setBestRent] = useState<TopScoredListing | null>(null);

    // Fetch listings with pagination
    const fetchListings = useCallback(async (offset: number, type: FilterType, sort: SortOption, append: boolean = false) => {
        const typeParam = type === 'all' ? '' : `&type=${type}`;
        const res = await fetch(`/api/tag/${slug}?limit=${PAGE_SIZE}&offset=${offset}${typeParam}&sort=${sort}`);

        if (!res.ok) {
            if (res.status === 404) {
                throw new Error('Tag no encontrado');
            }
            throw new Error('Failed to fetch');
        }

        const data = await res.json();

        if (append) {
            setListings(prev => [...prev, ...data.listings]);
        } else {
            setListings(data.listings || []);
        }

        setTagName(data.tag);
        setPagination(data.pagination);
        return data;
    }, [slug]);

    // Initial load
    useEffect(() => {
        async function fetchData() {
            setIsLoading(true);
            setError(null);
            try {
                await fetchListings(0, filter, sortBy);
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
                            {tagName || 'Cargando...'}
                        </h1>
                        <p className="text-[var(--text-secondary)] mt-1">
                            {pagination.total} propiedades
                            {listings.length < pagination.total && ` • Mostrando ${listings.length}`}
                        </p>
                    </div>

                    {/* Filters and Sort */}
                    <div className="flex flex-wrap items-center gap-4">
                        <div className="pill-group">
                            <Link
                                href={`/tag/${slug}`}
                                className={`pill-btn ${filter === 'all' ? 'active' : ''}`}
                            >
                                Todos
                            </Link>
                            <Link
                                href={`/tag/${slug}/venta`}
                                className={`pill-btn ${filter === 'sale' ? 'active' : ''}`}
                            >
                                Venta
                            </Link>
                            <Link
                                href={`/tag/${slug}/alquiler`}
                                className={`pill-btn ${filter === 'rent' ? 'active' : ''}`}
                            >
                                Renta
                            </Link>
                        </div>
                        <select
                            value={sortBy}
                            onChange={(e) => setSortBy(e.target.value as SortOption)}
                            className="border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                        >
                            <option value="price_asc">Precio: menor a mayor</option>
                            <option value="price_desc">Precio: mayor a menor</option>
                            <option value="recent">Más recientes</option>
                        </select>
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
                        {/* Listings Grid */}
                        {listingsForCard.length > 0 ? (
                            <>
                                <h2 className="text-lg font-semibold text-[var(--text-primary)] mb-4">
                                    Todas las propiedades
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
                                    No hay propiedades {filter === 'sale' ? 'en venta' : filter === 'rent' ? 'en renta' : ''} con este tag.
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
