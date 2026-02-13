'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import Navbar from '@/components/Navbar';
import LazyImage from '@/components/LazyImage';
import ListingModal from '@/components/ListingModal';
import { useFavorites } from '@/hooks/useFavorites';

interface FavoriteListing {
    external_id: string | number;
    title: string;
    price: number;
    currency: string;
    listing_type: 'sale' | 'rent';
    images: string[];
    specs: Record<string, string | number | undefined>;
    location: any;
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

export default function FavoritosPage() {
    const { favorites, removeFavorite, clearFavorites, favoriteCount } = useFavorites();
    const [listings, setListings] = useState<FavoriteListing[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [selectedId, setSelectedId] = useState<string | number | null>(null);
    const [compareMode, setCompareMode] = useState(false);
    const [compareIds, setCompareIds] = useState<Set<string>>(new Set());
    const [showingComparison, setShowingComparison] = useState(false);

    // Fetch full data for each favorite
    useEffect(() => {
        if (favorites.size === 0) {
            setListings([]);
            setIsLoading(false);
            return;
        }

        setIsLoading(true);
        const ids = [...favorites];
        Promise.all(
            ids.map(id =>
                fetch(`/api/listing/${id}`)
                    .then(res => res.ok ? res.json() : null)
                    .catch(() => null)
            )
        ).then(results => {
            setListings(results.filter(Boolean));
            setIsLoading(false);
        });
    }, [favorites]);

    const toggleCompare = (id: string | number) => {
        setCompareIds(prev => {
            const next = new Set(prev);
            const key = String(id);
            if (next.has(key)) {
                next.delete(key);
            } else if (next.size < 4) {
                next.add(key);
            }
            return next;
        });
    };

    const comparedListings = listings.filter(l => compareIds.has(String(l.external_id)));

    return (
        <>
            <Navbar />

            <main className="min-h-screen" style={{ background: 'var(--bg-page)' }}>
                <div className="container mx-auto px-4 max-w-7xl py-6">
                    {/* Header */}
                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
                        <div>
                            <Link href="/" className="text-sm text-[var(--primary)] hover:underline mb-2 inline-block no-underline">
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
                                    onClick={() => { setCompareMode(!compareMode); setCompareIds(new Set()); setShowingComparison(false); }}
                                    className={`px-4 py-2 rounded-lg text-sm font-semibold transition-all ${
                                        compareMode
                                            ? 'bg-[var(--primary)] text-white'
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

                    {/* Compare bar */}
                    {compareMode && compareIds.size > 0 && (
                        <div className="mb-6 bg-[var(--primary)] text-white rounded-xl p-4 flex items-center justify-between">
                            <span className="text-sm font-medium">
                                {compareIds.size} seleccionada{compareIds.size > 1 ? 's' : ''} (máx. 4)
                            </span>
                            <button
                                onClick={() => setShowingComparison(true)}
                                className={`px-4 py-1.5 rounded-lg text-sm font-bold transition-all ${
                                    compareIds.size < 2
                                        ? 'bg-white/50 text-[var(--primary)]/50 cursor-not-allowed'
                                        : 'bg-white text-[var(--primary)] hover:bg-slate-100'
                                }`}
                                disabled={compareIds.size < 2}
                            >
                                Ver comparación
                            </button>
                        </div>
                    )}

                    {/* Loading state */}
                    {isLoading && (
                        <div className="flex items-center justify-center py-20">
                            <div className="w-10 h-10 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
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
                                                setSelectedId(listing.external_id);
                                            }
                                        }}
                                    >
                                        {/* Image */}
                                        <div className="relative aspect-[4/3] overflow-hidden">
                                            <LazyImage
                                                src={listing.images?.[0] || '/placeholder.webp'}
                                                alt={listing.title || 'Propiedad'}
                                                className="w-full h-full"
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

                                            {/* Remove button */}
                                            {!compareMode && (
                                                <button
                                                    onClick={(e) => { e.stopPropagation(); removeFavorite(listing.external_id); }}
                                                    className="absolute top-3 right-3 p-1.5 rounded-full bg-red-500 text-white hover:bg-red-600 transition-all shadow-sm z-10"
                                                    aria-label="Quitar de favoritos"
                                                    title="Quitar de favoritos"
                                                >
                                                    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" strokeWidth="2">
                                                        <path strokeLinecap="round" strokeLinejoin="round" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
                                                    </svg>
                                                </button>
                                            )}
                                        </div>

                                        {/* Content */}
                                        <div className="p-4">
                                            <div className="text-xl font-black text-[#272727] tracking-tight mb-1">
                                                {formatPrice(listing.price)}
                                                {listing.listing_type === 'rent' && (
                                                    <span className="text-sm font-normal text-slate-500 ml-1">/mes</span>
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
                                className="text-sm text-[var(--primary)] hover:underline font-medium"
                            >
                                &larr; Volver a selección
                            </button>
                        </div>
                        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="border-b border-slate-200">
                                        <th className="text-left p-4 font-semibold text-slate-500 w-36">Característica</th>
                                        {comparedListings.map(l => (
                                            <th key={String(l.external_id)} className="p-4 text-center min-w-[200px]">
                                                <div className="w-full aspect-[4/3] rounded-lg overflow-hidden mb-2">
                                                    <img
                                                        src={l.images?.[0] || '/placeholder.webp'}
                                                        alt={l.title || 'Propiedad'}
                                                        className="w-full h-full object-cover"
                                                    />
                                                </div>
                                                <span className="text-xs text-slate-500 font-normal line-clamp-1">{l.title}</span>
                                            </th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr className="border-b border-slate-100">
                                        <td className="p-4 font-semibold text-slate-500">Precio</td>
                                        {comparedListings.map(l => (
                                            <td key={String(l.external_id)} className="p-4 text-center font-black text-lg text-[#272727]">
                                                {formatPrice(l.price)}
                                                {l.listing_type === 'rent' && <span className="text-xs font-normal text-slate-400">/mes</span>}
                                            </td>
                                        ))}
                                    </tr>
                                    <tr className="border-b border-slate-100">
                                        <td className="p-4 font-semibold text-slate-500">Tipo</td>
                                        {comparedListings.map(l => (
                                            <td key={String(l.external_id)} className="p-4 text-center">
                                                <span className={`inline-block px-2 py-0.5 rounded text-xs font-bold uppercase ${
                                                    l.listing_type === 'sale' ? 'bg-blue-100 text-blue-700' : 'bg-green-100 text-green-700'
                                                }`}>
                                                    {l.listing_type === 'sale' ? 'Venta' : 'Renta'}
                                                </span>
                                            </td>
                                        ))}
                                    </tr>
                                    <tr className="border-b border-slate-100">
                                        <td className="p-4 font-semibold text-slate-500">Habitaciones</td>
                                        {comparedListings.map(l => (
                                            <td key={String(l.external_id)} className="p-4 text-center font-bold">{l.specs?.bedrooms ?? '—'}</td>
                                        ))}
                                    </tr>
                                    <tr className="border-b border-slate-100">
                                        <td className="p-4 font-semibold text-slate-500">Baños</td>
                                        {comparedListings.map(l => (
                                            <td key={String(l.external_id)} className="p-4 text-center font-bold">{l.specs?.bathrooms ?? '—'}</td>
                                        ))}
                                    </tr>
                                    <tr className="border-b border-slate-100">
                                        <td className="p-4 font-semibold text-slate-500">Área (m²)</td>
                                        {comparedListings.map(l => {
                                            const a = getArea(l.specs);
                                            return (
                                                <td key={String(l.external_id)} className="p-4 text-center font-bold">
                                                    {a > 0 ? a.toLocaleString() : '—'}
                                                </td>
                                            );
                                        })}
                                    </tr>
                                    <tr className="border-b border-slate-100">
                                        <td className="p-4 font-semibold text-slate-500">Parqueo</td>
                                        {comparedListings.map(l => (
                                            <td key={String(l.external_id)} className="p-4 text-center font-bold">{l.specs?.parking ?? '—'}</td>
                                        ))}
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

            {/* Listing Modal */}
            {selectedId && (
                <ListingModal externalId={selectedId} onClose={() => setSelectedId(null)} />
            )}
        </>
    );
}
