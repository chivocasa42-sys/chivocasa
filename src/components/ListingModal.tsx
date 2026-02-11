'use client';

import { useState, useEffect } from 'react';
import LazyImage from './LazyImage';

interface ListingModalProps {
    externalId: string | number; // Can be string to prevent precision loss
    onClose: () => void;
}

interface FullListing {
    id: number;
    external_id: number;
    url: string;
    source: string;
    title: string;
    price: number;
    currency: string;
    location: any;
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

    // Priority: area_m2 (normalized by scraper) > fallback fields
    // area_m2 can be stored as string or number
    if (specs.area_m2) {
        const numValue = parseFloat(String(specs.area_m2));
        if (numValue > 0) return numValue;
    }

    // Fallback for legacy data
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

// Use location tags from the listing
function getLocationTags(listingTags: string[] | null | undefined, location: any): string[] {
    // Tags to exclude from display (all listings are in El Salvador, so redundant)
    const excludedTags = ['el salvador', 'no identificado'];

    if (listingTags && listingTags.length > 0) {
        return listingTags.filter(t => !excludedTags.includes(t.toLowerCase()));
    }

    // Fallback to building from location
    const tags: string[] = [];
    if (location?.municipio_detectado) tags.push(location.municipio_detectado);
    if (location?.departamento) tags.push(location.departamento);
    return tags;
}

export default function ListingModal({ externalId, onClose }: ListingModalProps) {
    const [listing, setListing] = useState<FullListing | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [currentImageIndex, setCurrentImageIndex] = useState(0);
    const [reverseGeoName, setReverseGeoName] = useState<string | null>(null);

    // Fetch full listing data
    useEffect(() => {
        async function fetchListing() {
            try {
                setIsLoading(true);
                const res = await fetch(`/api/listing/${externalId}`);
                if (!res.ok) {
                    throw new Error('Failed to fetch listing');
                }
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

    // Reverse geocode coords to get location name
    useEffect(() => {
        if (!listing) return;
        const lat = listing.location?.latitude;
        const lng = listing.location?.longitude;
        if (!lat || !lng) return;

        fetch(`/api/reverse-geocode?lat=${lat}&lng=${lng}`)
            .then(res => res.json())
            .then(data => {
                if (data.name) setReverseGeoName(data.name);
            })
            .catch(() => {});
    }, [listing]);

    // Keyboard navigation
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onClose();
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
            <div className="fixed inset-0 z-[100] bg-black/40 backdrop-blur-sm flex items-center justify-center p-4" onClick={onClose} role="dialog" aria-modal="true" aria-label="Cargando propiedad">
                <div className="bg-white w-full max-w-sm mx-auto rounded-xl shadow-2xl p-8 flex items-center justify-center min-h-[200px]" onClick={(e) => e.stopPropagation()}>
                    <div className="flex flex-col items-center gap-4">
                        <div className="w-10 h-10 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
                        <span className="text-slate-500 text-sm">Cargando...</span>
                    </div>
                </div>
            </div>
        );
    }

    if (error || !listing) {
        return (
            <div className="fixed inset-0 z-[100] bg-black/40 backdrop-blur-sm flex items-center justify-center p-4" onClick={onClose} role="dialog" aria-modal="true" aria-label="Error al cargar propiedad">
                <div className="bg-white w-full max-w-sm mx-auto rounded-xl shadow-2xl p-6 text-center" onClick={(e) => e.stopPropagation()}>
                    <div className="text-red-500 mb-3">
                        <svg className="w-12 h-12 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                        </svg>
                    </div>
                    <p className="text-slate-600 mb-4">{error || 'No se pudo cargar'}</p>
                    <button onClick={onClose} className="bg-slate-100 hover:bg-slate-200 text-slate-700 px-6 py-2 rounded-lg font-medium">
                        Cerrar
                    </button>
                </div>
            </div>
        );
    }

    const specs = listing.specs || {};
    const area = getArea(specs);
    const tags = getLocationTags(listing.tags, listing.location);
    const municipio = listing.location?.municipio_detectado;

    const hasMap = listing.location?.latitude && listing.location?.longitude;

    return (
        <div className="fixed inset-0 z-[100] bg-black/40 backdrop-blur-sm overflow-y-auto flex items-center justify-center p-3 md:p-4" onClick={onClose} role="dialog" aria-modal="true" aria-label="Detalles de propiedad">
            <div className="relative bg-white w-full max-w-3xl rounded-xl shadow-2xl overflow-hidden max-h-[95vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
                {/* Image Carousel - compact 16:9 */}
                <div className="relative bg-slate-900">
                    {/* Close Button - inside the image area */}
                    <button
                        onClick={onClose}
                        className="absolute top-2 right-2 z-50 p-2 rounded-full bg-black/50 hover:bg-black/70 text-white transition-all"
                        aria-label="Cerrar"
                    >
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>

                    <div className="relative w-full aspect-[16/9]">
                        {images.length > 0 ? (
                            <img
                                src={images[currentImageIndex]}
                                alt={`Imagen ${currentImageIndex + 1}`}
                                className="absolute inset-0 w-full h-full object-contain bg-slate-900"
                                loading="lazy"
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
                                onClick={(e) => { e.stopPropagation(); goToPrev(); }}
                                className="absolute left-2 top-1/2 -translate-y-1/2 p-2 rounded-full bg-white/90 hover:bg-white shadow-lg transition-all"
                                aria-label="Imagen anterior"
                            >
                                <svg className="w-5 h-5 text-slate-700" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 19l-7-7 7-7" />
                                </svg>
                            </button>
                            <button
                                onClick={(e) => { e.stopPropagation(); goToNext(); }}
                                className="absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-full bg-white/90 hover:bg-white shadow-lg transition-all"
                                aria-label="Imagen siguiente"
                            >
                                <svg className="w-5 h-5 text-slate-700" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
                                </svg>
                            </button>
                        </>
                    )}

                    {/* Image Counter */}
                    {images.length > 1 && (
                        <div className="absolute bottom-2 left-1/2 -translate-x-1/2 bg-black/60 text-white text-xs px-2.5 py-0.5 rounded-full">
                            {currentImageIndex + 1} / {images.length}
                        </div>
                    )}

                    {/* Sale/Rent Badge */}
                    <div className="absolute top-2 left-2 bg-white/95 backdrop-blur-sm px-2 py-0.5 rounded text-[11px] font-bold uppercase tracking-wide text-slate-800 flex items-center gap-1.5 shadow">
                        <span className="w-2 h-2 rounded-full bg-red-500"></span>
                        {listing.listing_type === 'sale' ? 'En Venta' : 'En Renta'}
                    </div>
                </div>

                {/* Thumbnail Strip - compact */}
                {images.length > 1 && (
                    <div className="bg-slate-100 p-1 flex gap-0.5 overflow-x-auto scrollbar-hide">
                        {images.map((img, idx) => (
                            <button
                                key={idx}
                                onClick={() => setCurrentImageIndex(idx)}
                                className={`flex-shrink-0 w-12 h-8 md:w-14 md:h-10 rounded overflow-hidden border-2 transition-all ${idx === currentImageIndex
                                    ? 'border-blue-500 ring-1 ring-blue-500'
                                    : 'border-transparent hover:border-slate-300'
                                    }`}
                            >
                                <img
                                    src={img}
                                    alt={`Miniatura ${idx + 1}`}
                                    className="w-full h-full object-cover"
                                    loading="lazy"
                                />
                            </button>
                        ))}
                    </div>
                )}

                {/* Content Section - two columns on desktop */}
                <div className="p-3 md:p-4">
                    <div className="flex flex-col md:flex-row md:gap-4">
                        {/* Left column: Price, specs, location, tags */}
                        <div className="flex-1 min-w-0">
                            {/* Price */}
                            <div className="text-2xl md:text-3xl font-black text-[#272727] tracking-tight mb-2">
                                {formatPrice(listing.price)}
                                {listing.listing_type === 'rent' && (
                                    <span className="text-sm font-normal text-slate-400 ml-1">/mes</span>
                                )}
                            </div>

                            {/* Specs - below price on mobile, inline on desktop */}
                            <div className="flex gap-4 mb-2">
                                {specs.bedrooms && (
                                    <div className="flex items-center gap-1">
                                        <span className="text-base font-bold text-[#272727]">{specs.bedrooms}</span>
                                        <span className="text-xs text-slate-500">hab</span>
                                    </div>
                                )}
                                {specs.bathrooms && (
                                    <div className="flex items-center gap-1">
                                        <span className="text-base font-bold text-[#272727]">{specs.bathrooms}</span>
                                        <span className="text-xs text-slate-500">baños</span>
                                    </div>
                                )}
                                {area > 0 && (
                                    <div className="flex items-center gap-1">
                                        <span className="text-base font-bold text-[#272727]">{area.toLocaleString()}</span>
                                        <span className="text-xs text-slate-500">m²</span>
                                    </div>
                                )}
                                {(specs.parking || specs.parqueo || specs.parqueos || specs.garages || specs.estacionamiento) && (
                                    <div className="flex items-center gap-1">
                                        <span className="text-base font-bold text-[#272727]">{specs.parking || specs.parqueo || specs.parqueos || specs.garages || specs.estacionamiento}</span>
                                        <span className="text-xs text-slate-500">parqueo</span>
                                    </div>
                                )}
                            </div>

                            {/* Location */}
                            {(municipio || reverseGeoName) && (
                                <div className="text-slate-500 text-sm mb-2 flex items-center gap-1.5">
                                    <svg className="w-3.5 h-3.5 flex-shrink-0" fill="currentColor" viewBox="0 0 16 16">
                                        <path d="M8 16s6-5.686 6-10A6 6 0 0 0 2 6c0 4.314 6 10 6 10zm0-7a3 3 0 1 1 0-6 3 3 0 0 1 0 6z" />
                                    </svg>
                                    {municipio || reverseGeoName}
                                </div>
                            )}

                            {/* Tags */}
                            {tags.length > 0 && (
                                <div className="flex flex-wrap gap-1.5 mb-3 md:mb-0">
                                    {tags.map((tag, idx) => (
                                        <span
                                            key={idx}
                                            className="bg-slate-100 text-slate-700 text-xs font-medium px-2 py-0.5 rounded-lg"
                                        >
                                            {tag}
                                        </span>
                                    ))}
                                </div>
                            )}
                        </div>

                        {/* Right column: Map + CTA */}
                        <div className="md:w-52 lg:w-56 flex-shrink-0 flex flex-col gap-2">
                            {/* Map Preview - compact */}
                            {hasMap && (
                                <a
                                    href={`https://www.google.com/maps?q=${listing.location.latitude},${listing.location.longitude}`}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="block rounded-lg overflow-hidden border border-slate-200 hover:border-blue-400 transition-all hover:shadow-md"
                                >
                                    <div className="relative">
                                        <img
                                            src={`https://static-maps.yandex.ru/1.x/?ll=${listing.location.longitude},${listing.location.latitude}&z=15&size=400,150&l=map&pt=${listing.location.longitude},${listing.location.latitude},pm2rdm`}
                                            alt="Ubicación en mapa"
                                            className="w-full h-[80px] md:h-[90px] object-cover"
                                            loading="lazy"
                                        />
                                        <div className="absolute bottom-1 right-1 bg-white/90 backdrop-blur-sm text-[10px] text-slate-600 px-1.5 py-0.5 rounded shadow flex items-center gap-0.5">
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
                                className="w-full bg-blue-600 hover:bg-blue-700 text-white py-2.5 px-4 rounded-lg font-bold text-sm text-center transition-all shadow-md hover:shadow-lg flex items-center justify-center gap-2"
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
    );
}
