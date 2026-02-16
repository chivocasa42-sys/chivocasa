'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Image from 'next/image';
import Navbar from '@/components/Navbar';
import { useFavorites } from '@/hooks/useFavorites';

interface FullListing {
    id: number;
    external_id: number;
    url: string;
    source: string;
    title: string;
    price: number;
    currency: string;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    location: Record<string, any> | null;
    listing_type: 'sale' | 'rent';
    description: string;
    specs: Record<string, string | number | undefined>;
    details: Record<string, string>;
    images: string[];
    contact_info: Record<string, string>;
    tags?: string[] | null;
    published_date: string;
    scraped_at: string;
    last_updated: string;
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
    const areaFields = ['Área construida (m²)', 'area', 'terreno', 'Área del terreno', 'm2', 'metros'];
    for (const field of areaFields) {
        const value = specs[field];
        if (value) {
            const numValue = parseFloat(String(value).replace(/[^\d.]/g, ''));
            if (numValue > 0) return numValue;
        }
    }
    return 0;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function getLocationTags(listingTags: string[] | null | undefined, location: Record<string, any> | null): string[] {
    const excludedTags = ['el salvador', 'no identificado'];
    if (listingTags && listingTags.length > 0) {
        return listingTags.filter((t: string) => !excludedTags.includes(t.toLowerCase()));
    }
    const tags: string[] = [];
    if (location?.municipio_detectado) tags.push(location.municipio_detectado);
    if (location?.departamento) tags.push(location.departamento);
    return tags;
}

export default function InmueblePage() {
    const params = useParams();
    const router = useRouter();
    const externalId = params.id as string;

    const [listing, setListing] = useState<FullListing | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [currentImageIndex, setCurrentImageIndex] = useState(0);
    const [reverseGeoName, setReverseGeoName] = useState<string | null>(null);
    const { isFavorite, toggleFavorite } = useFavorites();
    const liked = isFavorite(externalId);

    useEffect(() => {
        async function fetchListing() {
            try {
                setIsLoading(true);
                const res = await fetch(`/api/listing/${externalId}`);
                if (!res.ok) throw new Error('Failed to fetch listing');
                const data = await res.json();
                setListing(data);
            } catch (err) {
                setError(err instanceof Error ? err.message : 'Error loading listing');
            } finally {
                setIsLoading(false);
            }
        }
        fetchListing();
    }, [externalId]);

    useEffect(() => {
        if (!listing) return;
        const lat = listing.location?.latitude;
        const lng = listing.location?.longitude;
        if (!lat || !lng) return;
        fetch(`/api/reverse-geocode?lat=${lat}&lng=${lng}`)
            .then(res => res.json())
            .then(data => { if (data.name) setReverseGeoName(data.name); })
            .catch(() => {});
    }, [listing]);

    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'ArrowLeft') goToPrev();
            if (e.key === 'ArrowRight') goToNext();
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    });

    const images = (listing?.images || []).slice(0, 5);
    const goToNext = () => setCurrentImageIndex((prev) => (prev + 1) % images.length);
    const goToPrev = () => setCurrentImageIndex((prev) => (prev - 1 + images.length) % images.length);

    if (isLoading) {
        return (
            <>
                <Navbar />
                <main className="min-h-screen bg-slate-50">
                    <div className="container mx-auto px-4 max-w-4xl py-10">
                        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                            <div className="w-full aspect-video bg-slate-200 animate-pulse" />
                            <div className="p-6">
                                <div className="h-8 bg-slate-200 rounded w-1/3 mb-4 animate-pulse" />
                                <div className="h-4 bg-slate-200 rounded w-1/2 mb-3 animate-pulse" />
                                <div className="h-4 bg-slate-200 rounded w-2/3 animate-pulse" />
                            </div>
                        </div>
                    </div>
                </main>
            </>
        );
    }

    if (error || !listing) {
        return (
            <>
                <Navbar />
                <main className="min-h-screen bg-slate-50 flex items-center justify-center">
                    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-8 text-center max-w-sm">
                        <div className="text-red-500 mb-3">
                            <svg className="w-12 h-12 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                            </svg>
                        </div>
                        <p className="text-slate-600 mb-4">{error || 'Propiedad no encontrada'}</p>
                        <button onClick={() => router.back()} className="bg-slate-100 hover:bg-slate-200 text-slate-700 px-6 py-2 rounded-lg font-medium">
                            Volver
                        </button>
                    </div>
                </main>
            </>
        );
    }

    const specs = listing.specs || {};
    const area = getArea(specs);
    const tags = getLocationTags(listing.tags, listing.location);
    const municipio = listing.location?.municipio_detectado;
    const hasMap = listing.location?.latitude && listing.location?.longitude;

    return (
        <>
            <Navbar />
            <main className="min-h-screen bg-slate-50">
                <div className="container mx-auto px-4 max-w-4xl py-6">
                    {/* Back button */}
                    <button
                        onClick={() => router.back()}
                        className="text-sm text-blue-600 hover:underline font-medium mb-4 inline-flex items-center gap-1"
                    >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 19l-7-7 7-7" />
                        </svg>
                        Volver
                    </button>

                    <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                        {/* Image Carousel */}
                        <div className="relative bg-slate-900">
                            <div className="relative w-full aspect-video">
                                {images.length > 0 ? (
                                    <Image
                                        src={images[currentImageIndex]}
                                        alt={`Imagen ${currentImageIndex + 1}`}
                                        fill
                                        className="object-contain"
                                        priority
                                    />
                                ) : (
                                    <div className="absolute inset-0 flex items-center justify-center text-slate-500">
                                        Sin imágenes disponibles
                                    </div>
                                )}
                            </div>

                            {/* Navigation Arrows */}
                            {images.length > 1 && (
                                <>
                                    <button
                                        onClick={goToPrev}
                                        className="absolute left-3 top-1/2 -translate-y-1/2 p-2.5 rounded-full bg-white/90 hover:bg-white shadow-lg transition-all"
                                        aria-label="Imagen anterior"
                                    >
                                        <svg className="w-5 h-5 text-slate-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 19l-7-7 7-7" />
                                        </svg>
                                    </button>
                                    <button
                                        onClick={goToNext}
                                        className="absolute right-3 top-1/2 -translate-y-1/2 p-2.5 rounded-full bg-white/90 hover:bg-white shadow-lg transition-all"
                                        aria-label="Imagen siguiente"
                                    >
                                        <svg className="w-5 h-5 text-slate-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
                                        </svg>
                                    </button>
                                </>
                            )}

                            {/* Image Counter */}
                            {images.length > 1 && (
                                <div className="absolute bottom-3 left-1/2 -translate-x-1/2 bg-black/60 text-white text-xs px-3 py-1 rounded-full">
                                    {currentImageIndex + 1} / {images.length}
                                </div>
                            )}

                            {/* Sale/Rent Badge */}
                            <div className="absolute top-3 left-3 bg-white/95 backdrop-blur-sm px-3 py-1 rounded-md text-xs font-bold uppercase tracking-wide text-slate-800 flex items-center gap-1.5 shadow">
                                <span className="w-2 h-2 rounded-full bg-red-500"></span>
                                {listing.listing_type === 'sale' ? 'En Venta' : 'En Renta'}
                            </div>
                        </div>

                        {/* Thumbnail Strip */}
                        {images.length > 1 && (
                            <div className="bg-slate-100 p-1.5 flex gap-1 overflow-x-auto scrollbar-hide">
                                {images.map((img, idx) => (
                                    <button
                                        key={idx}
                                        onClick={() => setCurrentImageIndex(idx)}
                                        className={`shrink-0 w-16 h-12 rounded-md overflow-hidden border-2 transition-all ${idx === currentImageIndex
                                            ? 'border-blue-500 ring-1 ring-blue-500'
                                            : 'border-transparent hover:border-slate-300'
                                        }`}
                                    >
                                        <Image
                                            src={img}
                                            alt={`Miniatura ${idx + 1}`}
                                            width={64}
                                            height={48}
                                            className="w-full h-full object-cover"
                                        />
                                    </button>
                                ))}
                            </div>
                        )}

                        {/* Content Section */}
                        <div className="p-5 md:p-6">
                            <div className="flex flex-col md:flex-row md:gap-6">
                                {/* Left column: Price, specs, location, tags */}
                                <div className="flex-1 min-w-0">
                                    {/* Price */}
                                    <div className="text-3xl md:text-4xl font-black text-[#272727] tracking-tight mb-3">
                                        {formatPrice(listing.price)}
                                        {listing.listing_type === 'rent' && (
                                            <span className="text-sm font-normal text-slate-400 ml-1">/mes</span>
                                        )}
                                    </div>

                                    {/* Specs */}
                                    <div className="flex gap-5 mb-3">
                                        {specs.bedrooms && (
                                            <div className="flex items-center gap-1.5">
                                                <span className="text-lg font-bold text-[#272727]">{specs.bedrooms}</span>
                                                <span className="text-sm text-slate-500">hab</span>
                                            </div>
                                        )}
                                        {specs.bathrooms && (
                                            <div className="flex items-center gap-1.5">
                                                <span className="text-lg font-bold text-[#272727]">{specs.bathrooms}</span>
                                                <span className="text-sm text-slate-500">baños</span>
                                            </div>
                                        )}
                                        {area > 0 && (
                                            <div className="flex items-center gap-1.5">
                                                <span className="text-lg font-bold text-[#272727]">{area.toLocaleString()}</span>
                                                <span className="text-sm text-slate-500">m²</span>
                                            </div>
                                        )}
                                        {specs.parking && (
                                            <div className="flex items-center gap-1.5">
                                                <span className="text-lg font-bold text-[#272727]">{specs.parking}</span>
                                                <span className="text-sm text-slate-500">parq</span>
                                            </div>
                                        )}
                                    </div>

                                    {/* Location */}
                                    {(municipio || reverseGeoName) && (
                                        <div className="text-slate-500 text-sm mb-3 flex items-center gap-1.5">
                                            <svg className="w-4 h-4 shrink-0" fill="currentColor" viewBox="0 0 16 16">
                                                <path d="M8 16s6-5.686 6-10A6 6 0 0 0 2 6c0 4.314 6 10 6 10zm0-7a3 3 0 1 1 0-6 3 3 0 0 1 0 6z" />
                                            </svg>
                                            {municipio || reverseGeoName}
                                        </div>
                                    )}

                                    {/* Tags */}
                                    {tags.length > 0 && (
                                        <div className="flex flex-wrap gap-1.5 mb-4">
                                            {tags.map((tag, idx) => (
                                                <span
                                                    key={idx}
                                                    className="bg-slate-100 text-slate-700 text-xs font-medium px-2.5 py-1 rounded-lg"
                                                >
                                                    {tag}
                                                </span>
                                            ))}
                                        </div>
                                    )}

                                    {/* Favorite Button */}
                                    <button
                                        onClick={() => toggleFavorite(externalId)}
                                        className="flex items-center gap-2 py-1.5 transition-colors group/fav"
                                        aria-label={liked ? 'Quitar de favoritos' : 'Agregar a favoritos'}
                                    >
                                        <svg className="w-5 h-5" viewBox="0 0 24 24" fill={liked ? '#ef4444' : 'none'} stroke={liked ? '#ef4444' : '#94a3b8'} strokeWidth="2">
                                            <path strokeLinecap="round" strokeLinejoin="round" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
                                        </svg>
                                        <span className={`text-sm font-medium ${
                                            liked ? 'text-red-500' : 'text-slate-500 group-hover/fav:text-red-500'
                                        }`}>
                                            {liked ? 'Guardado en favoritos' : 'Agregar a favoritos'}
                                        </span>
                                    </button>

                                    {/* Share Button */}
                                    <button
                                        onClick={async () => {
                                            const shareUrl = window.location.href;
                                            const shareTitle = listing.title || 'Propiedad en SivarCasas';
                                            const shareText = `${shareTitle} - ${formatPrice(listing.price)}`;
                                            if (navigator.share) {
                                                try {
                                                    await navigator.share({ title: shareTitle, text: shareText, url: shareUrl });
                                                } catch { /* user cancelled */ }
                                            } else {
                                                await navigator.clipboard.writeText(shareUrl);
                                                alert('Enlace copiado al portapapeles');
                                            }
                                        }}
                                        className="flex items-center gap-2 py-1.5 transition-colors group/share"
                                        aria-label="Compartir"
                                    >
                                        <svg className="w-5 h-5 text-slate-400 group-hover/share:text-blue-500 transition-colors" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
                                        </svg>
                                        <span className="text-sm font-medium text-slate-500 group-hover/share:text-blue-500 transition-colors">
                                            Compartir
                                        </span>
                                    </button>
                                </div>

                                {/* Right column: Map + CTA */}
                                <div className="md:w-60 lg:w-64 shrink-0 flex flex-col gap-3 mt-4 md:mt-0">
                                    {/* Map Preview */}
                                    {hasMap && (
                                        <a
                                            href={`https://www.google.com/maps?q=${listing.location?.latitude},${listing.location?.longitude}`}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="block rounded-lg overflow-hidden border border-slate-200 hover:border-blue-400 transition-all hover:shadow-md"
                                        >
                                            <div className="relative">
                                                <Image
                                                    src={`https://static-maps.yandex.ru/1.x/?ll=${listing.location?.longitude},${listing.location?.latitude}&z=15&size=400,200&l=map&pt=${listing.location?.longitude},${listing.location?.latitude},pm2rdm`}
                                                    alt="Ubicación en mapa"
                                                    width={400}
                                                    height={200}
                                                    className="w-full h-[100px] md:h-[120px] object-cover"
                                                />
                                                <div className="absolute bottom-1.5 right-1.5 bg-white/90 backdrop-blur-sm text-[10px] text-slate-600 px-2 py-0.5 rounded shadow flex items-center gap-1">
                                                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                                                    </svg>
                                                    Google Maps
                                                </div>
                                            </div>
                                        </a>
                                    )}

                                    {/* CTA Button */}
                                    <a
                                        href={listing.url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="w-full bg-blue-600 hover:bg-blue-700 text-white py-3 px-4 rounded-lg font-bold text-sm text-center transition-all shadow-md hover:shadow-lg flex items-center justify-center gap-2"
                                    >
                                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                                        </svg>
                                        Ver más información
                                    </a>
                                    <div className="text-center text-[9px] text-slate-400 font-medium uppercase tracking-wide">
                                        Indexado por <span className="font-black italic text-slate-600">SIVAR<span className="text-blue-600">CASAS</span></span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </main>
        </>
    );
}
