'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { useRouter } from 'next/navigation';
import Navbar from '@/components/Navbar';
import LazyImage from '@/components/LazyImage';
import { useFavorites } from '@/hooks/useFavorites';

interface FavoriteListing {
    external_id: string | number;
    title: string;
    price: number;
    currency: string;
    listing_type: 'sale' | 'rent';
    images: string[];
    specs: Record<string, string | number | undefined>;
    location: {
        municipio_detectado?: string;
        departamento?: string;
        city?: string;
        state?: string;
        latitude?: number;
        longitude?: number;
        [key: string]: string | number | undefined;
    } | string | null;
    tags?: string[] | null;
    url: string;
    published_date: string;
}

function formatPrice(price: number): string {
    if (!price) return 'N/A';
    return '$' + price.toLocaleString('en-US');
}

function getArea(specs: Record<string, string | number | undefined> | null | undefined): number {
    if (!specs) return 0;
    if (specs.area_m2) {
        const numValue = parseFloat(String(specs.area_m2));
        if (numValue > 0) return numValue;
    }
    return 0;
}

// Helper functions to determine the best value for comparison
function getBestPrice(listings: FavoriteListing[]): number | null {
    const prices = listings.map(l => l.price).filter(p => p > 0);
    return prices.length > 0 ? Math.min(...prices) : null;
}

function getBestNumeric(specKey: keyof Record<string, string | number | undefined>, listings: FavoriteListing[]): number | null {
    const values = listings
        .map(l => {
            const val = l.specs?.[specKey];
            return val !== undefined && val !== null ? Number(val) : null;
        })
        .filter(v => v !== null && v > 0) as number[];
    return values.length > 0 ? Math.max(...values) : null;
}

function getBestArea(listings: FavoriteListing[]): number | null {
    const areas = listings.map(l => getArea(l.specs)).filter(a => a > 0);
    return areas.length > 0 ? Math.max(...areas) : null;
}

// Star icon component
function StarIcon({ className = "" }: { className?: string }) {
    return (
        <svg
            className={`w-4 h-4 text-yellow-500 ${className}`}
            viewBox="0 0 24 24"
            fill="currentColor"
            xmlns="http://www.w3.org/2000/svg"
        >
            <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
        </svg>
    );
}

export default function FavoritosPage() {
    const { favorites, removeFavorite, clearFavorites, favoriteCount } = useFavorites();
    const [listings, setListings] = useState<FavoriteListing[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const router = useRouter();
    const [compareMode, setCompareMode] = useState(false);
    const [compareIds, setCompareIds] = useState<Set<string>>(new Set());
    const [showingComparison, setShowingComparison] = useState(false);
    const [compareTypeWarning, setCompareTypeWarning] = useState<string | null>(null);

    // Fetch full data for all favorites in a single batch request
    useEffect(() => {
        const fetchFavorites = async () => {
            if (favorites.size === 0) {
                setListings([]);
                setIsLoading(false);
                return;
            }

            setIsLoading(true);
            const ids = [...favorites].join(',');

            try {
                const res = await fetch(`/api/listings/batch?ids=${ids}`);
                const data = res.ok ? await res.json() : [];
                setListings(data || []);
            } catch (error) {
                console.error('Error fetching favorites:', error);
                setListings([]);
            } finally {
                setIsLoading(false);
            }
        };

        fetchFavorites();
    }, [favorites]);

    const toggleCompare = useCallback((id: string | number) => {
        const key = String(id);
        const clickedListing = listings.find(l => String(l.external_id) === key);
        if (!clickedListing) return;

        setCompareIds(prev => {
            const next = new Set(prev);

            // If already selected, allow deselection
            if (next.has(key)) {
                next.delete(key);
                setCompareTypeWarning(null);
                return next;
            }

            // Check listing type matches existing selections
            if (next.size > 0) {
                const firstSelectedId = [...next][0];
                const firstListing = listings.find(l => String(l.external_id) === firstSelectedId);
                if (firstListing && firstListing.listing_type !== clickedListing.listing_type) {
                    setCompareTypeWarning(
                        'Solo puedes comparar propiedades del mismo tipo (todas en Venta o todas en Renta).'
                    );
                    return prev;
                }
            }

            if (next.size < 4) {
                next.add(key);
                setCompareTypeWarning(null);
            }
            return next;
        });
    }, [listings]);

    const comparedListings = listings.filter(l => compareIds.has(String(l.external_id)));

    // Calculate best values for comparison
    const bestPrice = comparedListings.length > 0 ? getBestPrice(comparedListings) : null;
    const bestBedrooms = comparedListings.length > 0 ? getBestNumeric('bedrooms', comparedListings) : null;
    const bestBathrooms = comparedListings.length > 0 ? getBestNumeric('bathrooms', comparedListings) : null;
    const bestArea = comparedListings.length > 0 ? getBestArea(comparedListings) : null;
    const bestParking = comparedListings.length > 0 ? getBestNumeric('parking', comparedListings) : null;

    return (
        <>
            <Navbar />

            <main className="min-h-screen bg-(--bg-page)">
                <div className="container mx-auto px-4 max-w-7xl py-6">
                    {/* Sticky Header with buttons */}
                    <div className="sticky top-14 z-30 bg-(--bg-page) py-4 mb-6 border-b border-slate-100 -mx-4 px-4">
                        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                            <div>
                                <Link href="/" className="text-sm text-(--primary) hover:underline mb-2 inline-block no-underline">
                                    &larr; Volver al inicio
                                </Link>
                                <h1 className="text-2xl md:text-3xl font-black text-[#272727] tracking-tight">
                                    Mis Favoritos
                                </h1>
                                <p className="text-slate-500 text-sm mt-1">
                                    {favoriteCount === 0
                                        ? 'No tienes propiedades guardadas'
                                        : `${favoriteCount} propiedad${favoriteCount > 1 ? 'es' : ''} guardada${favoriteCount > 1 ? 's' : ''}`
                                    }
                                </p>
                            </div>

                            {favoriteCount > 0 && (
                                <div className="flex items-center gap-2">
                                    <button
                                        onClick={() => { setCompareMode(!compareMode); setCompareIds(new Set()); setShowingComparison(false); setCompareTypeWarning(null); }}
                                        className={`px-4 py-2 rounded-lg text-sm font-semibold transition-all ${
                                            compareMode
                                                ? 'bg-(--primary) text-white'
                                                : 'bg-white border border-slate-200 text-slate-700 hover:bg-slate-50'
                                        }`}
                                    >
                                        {compareMode ? 'Cancelar comparar' : 'Comparar'}
                                    </button>
                                    <button
                                        onClick={() => { if (confirm('¿Eliminar todos los favoritos?')) clearFavorites(); }}
                                        className="px-4 py-2 rounded-lg text-sm font-semibold bg-white border border-red-200 text-red-500 hover:bg-red-50 transition-all"
                                    >
                                        Limpiar todo
                                    </button>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Type mismatch warning */}
                    {compareTypeWarning && (
                        <div className="mb-4 bg-amber-50 border border-amber-200 text-amber-800 rounded-lg px-4 py-3 flex items-center gap-2 text-sm">
                            <svg className="w-5 h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                            </svg>
                            <span>{compareTypeWarning}</span>
                            <button onClick={() => setCompareTypeWarning(null)} className="ml-auto text-amber-600 hover:text-amber-800">
                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /></svg>
                            </button>
                        </div>
                    )}

                    {/* Sticky Compare bar */}
                    {compareMode && compareIds.size > 0 && (
                        <div className="mb-6 bg-(--primary) text-white rounded-xl p-4 flex items-center justify-between shadow-lg">
                            <span className="text-sm font-medium">
                                {compareIds.size} seleccionada{compareIds.size > 1 ? 's' : ''} (máx. 4)
                            </span>
                            {!showingComparison && (
                                <button
                                    onClick={() => setShowingComparison(true)}
                                    className={`px-4 py-1.5 rounded-lg text-sm font-bold transition-all ${
                                        compareIds.size < 2
                                            ? 'bg-white/50 text-(--primary)/50 cursor-not-allowed'
                                            : 'bg-white text-(--primary) hover:bg-slate-100'
                                    }`}
                                    disabled={compareIds.size < 2}
                                >
                                    Ver comparación
                                </button>
                            )}
                        </div>
                    )}

                    {/* Loading state - skeleton cards */}
                    {isLoading && (
                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                            {[...Array(Math.min(favoriteCount || 4, 8))].map((_, i) => (
                                <div key={i} className="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
                                    <div className="skeleton-pulse w-full h-48 bg-slate-200"></div>
                                    <div className="p-4">
                                        <div className="skeleton-pulse h-4 bg-slate-200 rounded mb-2 w-3/4"></div>
                                        <div className="skeleton-pulse h-4 bg-slate-200 rounded mb-3 w-1/2"></div>
                                        <div className="skeleton-pulse h-3 bg-slate-200 rounded w-full"></div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}

                    {/* Empty state */}
                    {!isLoading && listings.length === 0 && (
                        <div className="text-center py-20">
                            <svg className="w-16 h-16 mx-auto text-slate-300 mb-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
                            </svg>
                            <h2 className="text-xl font-bold text-slate-600 mb-2">Sin favoritos aún</h2>
                            <p className="text-slate-400 mb-6">Toca el corazón en cualquier propiedad para guardarla aquí.</p>
                            <Link
                                href="/"
                                className="inline-block bg-[var(--primary)] text-white px-6 py-2.5 rounded-lg font-semibold hover:opacity-90 transition-all no-underline"
                            >
                                Explorar propiedades
                            </Link>
                        </div>
                    )}

                    {/* Grid vs comparison table */}
                    {!showingComparison ? (
                        /* Grid of favorite cards */
                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                            {listings.map(listing => {
                                const specs = listing.specs || {};
                                const area = getArea(specs);
                                const isSelected = compareIds.has(String(listing.external_id));

                                return (
                                    <article
                                        key={String(listing.external_id)}
                                        className={`bg-white rounded-lg shadow-sm border overflow-hidden transition-all ${
                                            compareMode
                                                ? isSelected
                                                    ? 'border-[var(--primary)] ring-2 ring-[var(--primary)]'
                                                    : 'border-slate-200 hover:border-[var(--primary)] cursor-pointer'
                                                : 'border-slate-200 hover:shadow-xl'
                                        }`}
                                        onClick={() => {
                                            if (compareMode) {
                                                toggleCompare(listing.external_id);
                                            } else {
                                                router.push(`/inmuebles/${listing.external_id}`);
                                            }
                                        }}
                                    >
                                        {/* Image */}
                                        <div className="relative aspect-[4/3] overflow-hidden">
                                            <LazyImage
                                                src={listing.images?.[0] || '/placeholder.webp'}
                                                alt={listing.title || 'Propiedad'}
                                                className="w-full h-full object-cover"
                                                placeholderSrc="/placeholder.webp"
                                            />

                                            {/* Compare checkbox overlay */}
                                            {compareMode && (
                                                <div className="absolute top-3 left-3 z-10">
                                                    <div className={`w-6 h-6 rounded-full border-2 flex items-center justify-center transition-all ${
                                                        isSelected
                                                            ? 'bg-[var(--primary)] border-[var(--primary)] text-white'
                                                            : 'bg-white/90 border-slate-300'
                                                    }`}>
                                                        {isSelected && (
                                                            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M5 13l4 4L19 7" />
                                                            </svg>
                                                        )}
                                                    </div>
                                                </div>
                                            )}

                                            {/* Type badge */}
                                            <div className={`absolute ${compareMode ? 'top-3 right-3' : 'top-3 left-3'}`}>
                                                <span className="bg-white/95 backdrop-blur-sm text-slate-800 text-[11px] font-bold px-2.5 py-1 rounded shadow-sm uppercase tracking-wide flex items-center gap-1.5">
                                                    <span className="w-1.5 h-1.5 rounded-full bg-red-500"></span>
                                                    {listing.listing_type === 'sale' ? 'En Venta' : 'En Renta'}
                                                </span>
                                            </div>

                                        </div>

                                        {/* Content */}
                                        <div className="p-4">
                                            {/* Price + Action Icons */}
                                            <div className="flex items-center justify-between mb-1">
                                                <div className="text-xl font-black text-[#272727] tracking-tight">
                                                    {formatPrice(listing.price)}
                                                    {listing.listing_type === 'rent' && (
                                                        <span className="text-sm font-normal text-slate-500 ml-1">/mes</span>
                                                    )}
                                                </div>
                                                {!compareMode && (
                                                    <div className="flex items-center gap-1 shrink-0">
                                                        {/* Share Button */}
                                                        <button
                                                            onClick={async (e) => {
                                                                e.stopPropagation();
                                                                const shareUrl = `${window.location.origin}/inmuebles/${listing.external_id}`;
                                                                if (navigator.share) {
                                                                    try {
                                                                        await navigator.share({ title: listing.title || 'Propiedad en SivarCasas', url: shareUrl });
                                                                    } catch { /* user cancelled */ }
                                                                } else {
                                                                    await navigator.clipboard.writeText(shareUrl);
                                                                    alert('Enlace copiado al portapapeles');
                                                                }
                                                            }}
                                                            className="p-1 transition-colors"
                                                            aria-label="Compartir"
                                                            title="Compartir"
                                                        >
                                                            <svg className="w-5 h-5 text-slate-400 hover:text-blue-500 transition-colors" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                                                                <path strokeLinecap="round" strokeLinejoin="round" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
                                                            </svg>
                                                        </button>
                                                        {/* Favorite Button (filled red, removes from favorites) */}
                                                        <button
                                                            onClick={(e) => { e.stopPropagation(); removeFavorite(listing.external_id); }}
                                                            className="p-1 transition-colors"
                                                            aria-label="Quitar de favoritos"
                                                            title="Quitar de favoritos"
                                                        >
                                                            <svg className="w-6 h-6" viewBox="0 0 24 24" fill="#ef4444" stroke="#ef4444" strokeWidth="2">
                                                                <path strokeLinecap="round" strokeLinejoin="round" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
                                                            </svg>
                                                        </button>
                                                    </div>
                                                )}
                                            </div>
                                            <div className="flex items-center gap-1.5 text-[13px] text-slate-700 font-medium mb-2">
                                                {specs.bedrooms !== undefined && (
                                                    <span><span className="font-bold">{specs.bedrooms}</span> hab</span>
                                                )}
                                                {specs.bedrooms !== undefined && specs.bathrooms !== undefined && <span className="text-slate-300">|</span>}
                                                {specs.bathrooms !== undefined && (
                                                    <span><span className="font-bold">{specs.bathrooms}</span> baños</span>
                                                )}
                                                {area > 0 && (
                                                    <>
                                                        <span className="text-slate-300">|</span>
                                                        <span><span className="font-bold">{area.toLocaleString()}</span> m²</span>
                                                    </>
                                                )}
                                            </div>
                                            {listing.tags && listing.tags.length > 0 && (
                                                <div className="flex flex-wrap gap-1">
                                                    {listing.tags.filter(t => t.toLowerCase() !== 'el salvador').slice(0, 3).map((tag, i) => (
                                                        <span key={i} className="bg-slate-100 text-slate-600 text-[11px] font-medium px-2 py-0.5 rounded">
                                                            {tag}
                                                        </span>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                    </article>
                                );
                            })}
                        </div>
                    ) : (
                        /* Side-by-side comparison table */
                        <>
                        <div className="mb-4">
                            <button
                                onClick={() => setShowingComparison(false)}
                                className="text-sm text-(--primary) hover:underline font-medium"
                            >
                                &larr; Volver a selección
                            </button>
                        </div>
                        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className={`border-b-2 ${comparedListings[0]?.listing_type === 'sale' ? 'border-blue-200 bg-blue-50' : 'border-red-200 bg-red-50'}`}>
                                        <th colSpan={comparedListings.length + 1} className="p-3 text-center">
                                            <span className={`text-lg font-bold uppercase tracking-wide ${comparedListings[0]?.listing_type === 'sale' ? 'text-blue-600' : 'text-red-500'}`}>
                                                {comparedListings[0]?.listing_type === 'sale' ? 'Venta' : 'Renta'}
                                            </span>
                                        </th>
                                    </tr>
                                    <tr className="border-b border-slate-200">
                                        <th className="text-left p-4 font-semibold text-slate-500 w-36"></th>
                                        {comparedListings.map(l => (
                                            <th key={String(l.external_id)} className="p-4 text-center min-w-[220px]">
                                                <div className="w-64 h-36 mx-auto rounded-lg overflow-hidden border border-slate-200">
                                                    <Image
                                                        src={l.images?.[0] || '/placeholder.webp'}
                                                        alt={l.title || 'Propiedad'}
                                                        width={256}
                                                        height={144}
                                                        className="w-full h-full object-cover"
                                                        priority={comparedListings.length <= 2}
                                                    />
                                                </div>
                                            </th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr className="border-b border-slate-100">
                                        <td className="p-4 font-semibold text-slate-500">Precio</td>
                                        {comparedListings.map(l => {
                                            const isBest = bestPrice !== null && l.price === bestPrice;
                                            return (
                                                <td key={String(l.external_id)} className={`p-4 text-center font-black text-lg ${isBest ? 'text-green-600' : 'text-[#272727]'}`}>
                                                    <div className="flex items-center justify-center gap-1">
                                                        {formatPrice(l.price)}
                                                        {isBest && <StarIcon />}
                                                    </div>
                                                    {l.listing_type === 'rent' && <span className="text-xs font-normal text-slate-400 block">/mes</span>}
                                                </td>
                                            );
                                        })}
                                    </tr>
                                    <tr className="border-b border-slate-100">
                                        <td className="p-4 font-semibold text-slate-500">Habitaciones</td>
                                        {comparedListings.map(l => {
                                            const bedrooms = l.specs?.bedrooms;
                                            const isBest = bestBedrooms !== null && bedrooms !== undefined && Number(bedrooms) === bestBedrooms;
                                            return (
                                                <td key={String(l.external_id)} className={`p-4 text-center font-bold ${isBest ? 'text-green-600' : ''}`}>
                                                    <div className="flex items-center justify-center gap-1">
                                                        {bedrooms ?? '—'}
                                                        {isBest && bedrooms !== undefined && <StarIcon />}
                                                    </div>
                                                </td>
                                            );
                                        })}
                                    </tr>
                                    <tr className="border-b border-slate-100">
                                        <td className="p-4 font-semibold text-slate-500">Baños</td>
                                        {comparedListings.map(l => {
                                            const bathrooms = l.specs?.bathrooms;
                                            const isBest = bestBathrooms !== null && bathrooms !== undefined && Number(bathrooms) === bestBathrooms;
                                            return (
                                                <td key={String(l.external_id)} className={`p-4 text-center font-bold ${isBest ? 'text-green-600' : ''}`}>
                                                    <div className="flex items-center justify-center gap-1">
                                                        {bathrooms ?? '—'}
                                                        {isBest && bathrooms !== undefined && <StarIcon />}
                                                    </div>
                                                </td>
                                            );
                                        })}
                                    </tr>
                                    <tr className="border-b border-slate-100">
                                        <td className="p-4 font-semibold text-slate-500">Área (m²)</td>
                                        {comparedListings.map(l => {
                                            const a = getArea(l.specs);
                                            const isBest = bestArea !== null && a > 0 && a === bestArea;
                                            return (
                                                <td key={String(l.external_id)} className={`p-4 text-center font-bold ${isBest ? 'text-green-600' : ''}`}>
                                                    <div className="flex items-center justify-center gap-1">
                                                        {a > 0 ? a.toLocaleString() : '—'}
                                                        {isBest && a > 0 && <StarIcon />}
                                                    </div>
                                                </td>
                                            );
                                        })}
                                    </tr>
                                    <tr className="border-b border-slate-100">
                                        <td className="p-4 font-semibold text-slate-500">Parqueo</td>
                                        {comparedListings.map(l => {
                                            const parking = l.specs?.parking;
                                            const isBest = bestParking !== null && parking !== undefined && Number(parking) === bestParking;
                                            return (
                                                <td key={String(l.external_id)} className={`p-4 text-center font-bold ${isBest ? 'text-green-600' : ''}`}>
                                                    <div className="flex items-center justify-center gap-1">
                                                        {parking ?? '—'}
                                                        {isBest && parking !== undefined && <StarIcon />}
                                                    </div>
                                                </td>
                                            );
                                        })}
                                    </tr>
                                    <tr className="border-b border-slate-100">
                                        <td className="p-4 font-semibold text-slate-500">Categoría</td>
                                        {comparedListings.map(l => (
                                            <td key={String(l.external_id)} className="p-4 text-center text-slate-600">
                                                {l.tags?.filter(t => t.toLowerCase() !== 'el salvador').slice(0, 2).join(', ') || '—'}
                                            </td>
                                        ))}
                                    </tr>
                                    <tr>
                                        <td className="p-4"></td>
                                        {comparedListings.map(l => (
                                            <td key={String(l.external_id)} className="p-4 text-center">
                                                <a
                                                    href={l.url}
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                    className="inline-block bg-blue-600 hover:bg-blue-700 text-white px-4 py-1.5 rounded-lg text-xs font-bold transition-all no-underline"
                                                >
                                                    Más Información
                                                </a>
                                            </td>
                                        ))}
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                        </>
                    )}
                </div>
            </main>

        </>
    );
}
