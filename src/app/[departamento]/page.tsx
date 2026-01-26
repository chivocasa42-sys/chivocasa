'use client';

import { useState, useEffect, useMemo } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import Navbar from '@/components/Navbar';
import ListingCard from '@/components/ListingCard';
import ListingModal from '@/components/ListingModal';
import BestOpportunitySection from '@/components/BestOpportunitySection';
import { slugToDepartamento } from '@/lib/slugify';

interface Listing {
    external_id: number;
    title: string;
    price: number;
    location: {
        departamento?: string;
        municipio_detectado?: string;
    } | null;
    listing_type: 'sale' | 'rent';
    url: string;
    specs: Record<string, string | number> | null;
    description: string;
    images: string[] | null;
    source: string;
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

type FilterType = 'all' | 'sale' | 'rent';

export default function DepartmentPage() {
    const params = useParams();
    const slug = params.departamento as string;
    const departamento = slugToDepartamento(slug);

    const [listings, setListings] = useState<Listing[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [filter, setFilter] = useState<FilterType>('all');
    const [selectedListing, setSelectedListing] = useState<Listing | null>(null);

    // Best opportunities
    const [bestSale, setBestSale] = useState<TopScoredListing | null>(null);
    const [bestRent, setBestRent] = useState<TopScoredListing | null>(null);

    useEffect(() => {
        async function fetchData() {
            setIsLoading(true);
            setError(null);
            try {
                // Fetch listings
                const listingsRes = await fetch(`/api/department/${slug}`);
                if (!listingsRes.ok) {
                    if (listingsRes.status === 404) {
                        setError('Departamento no encontrado');
                        return;
                    }
                    throw new Error('Failed to fetch');
                }
                const listingsData = await listingsRes.json();
                setListings(listingsData.listings || []);

                // Fetch best opportunities (single call, returns both)
                const topScoredRes = await fetch(`/api/department/${slug}/top-scored?type=all&limit=1`);
                if (topScoredRes.ok) {
                    const topScoredData = await topScoredRes.json();
                    setBestSale(topScoredData.sale?.[0] || null);
                    setBestRent(topScoredData.rent?.[0] || null);
                }
            } catch (err) {
                setError('No pudimos cargar los datos. Intentá de nuevo.');
                console.error(err);
            } finally {
                setIsLoading(false);
            }
        }

        if (slug) fetchData();
    }, [slug]);

    // Filtrar listings
    const filteredListings = useMemo(() => {
        if (filter === 'all') return listings;
        return listings.filter(l => l.listing_type === filter);
    }, [listings, filter]);

    // Stats
    const stats = useMemo(() => {
        const saleListings = listings.filter(l => l.listing_type === 'sale');
        const rentListings = listings.filter(l => l.listing_type === 'rent');
        return { total: listings.length, sale: saleListings.length, rent: rentListings.length };
    }, [listings]);

    // Handle view listing from best opportunity
    const handleViewBestListing = (topScored: TopScoredListing) => {
        // Find full listing or create minimal version
        const fullListing = listings.find(l => l.external_id === topScored.external_id);
        if (fullListing) {
            setSelectedListing(fullListing);
        } else {
            // Open URL directly
            window.open(topScored.url, '_blank');
        }
    };

    return (
        <>
            <Navbar
                totalListings={stats.total}
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
                            {stats.total} propiedades • {stats.sale} en venta • {stats.rent} en alquiler
                        </p>
                    </div>

                    {/* Filters */}
                    <div className="pill-group">
                        <button
                            onClick={() => setFilter('all')}
                            className={`pill-btn ${filter === 'all' ? 'active' : ''}`}
                        >
                            Todos ({stats.total})
                        </button>
                        <button
                            onClick={() => setFilter('sale')}
                            className={`pill-btn ${filter === 'sale' ? 'active' : ''}`}
                        >
                            Venta ({stats.sale})
                        </button>
                        <button
                            onClick={() => setFilter('rent')}
                            className={`pill-btn ${filter === 'rent' ? 'active' : ''}`}
                        >
                            Alquiler ({stats.rent})
                        </button>
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
                        {/* Best Opportunities */}
                        <BestOpportunitySection
                            saleListing={bestSale}
                            rentListing={bestRent}
                            onViewListing={handleViewBestListing}
                        />

                        {/* Listings Grid */}
                        {filteredListings.length > 0 ? (
                            <>
                                <h2 className="text-lg font-semibold text-[var(--text-primary)] mb-4">
                                    Todas las propiedades
                                </h2>
                                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
                                    {filteredListings.map((listing) => (
                                        <ListingCard
                                            key={listing.external_id}
                                            listing={listing}
                                            onClick={() => setSelectedListing(listing)}
                                        />
                                    ))}
                                </div>
                            </>
                        ) : (
                            <div className="card-float p-8 text-center">
                                <p className="text-[var(--text-secondary)]">
                                    No hay propiedades {filter === 'sale' ? 'en venta' : filter === 'rent' ? 'en alquiler' : ''} en este departamento.
                                </p>
                            </div>
                        )}
                    </>
                )}
            </main>

            {/* Modal */}
            {selectedListing && (
                <ListingModal
                    listing={selectedListing}
                    onClose={() => setSelectedListing(null)}
                />
            )}
        </>
    );
}
