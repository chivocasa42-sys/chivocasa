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

    // Priority: area_m2 (normalized) > specific fields > generic area
    if (specs.area_m2 && typeof specs.area_m2 === 'number') {
        return specs.area_m2;
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

// Use location tags from the listing
function getLocationTags(listingTags: string[] | null | undefined, location: any): string[] {
    if (listingTags && listingTags.length > 0) {
        return listingTags;
    }

    // Fallback to building from location
    const tags: string[] = [];
    if (location?.municipio_detectado) tags.push(location.municipio_detectado);
    if (location?.departamento) tags.push(location.departamento);
    tags.push('El Salvador');
    return tags;
}

export default function ListingModal({ externalId, onClose }: ListingModalProps) {
    const [listing, setListing] = useState<FullListing | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [currentImageIndex, setCurrentImageIndex] = useState(0);

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

    const images = listing?.images || [];
    const goToNext = () => setCurrentImageIndex((prev) => (prev + 1) % images.length);
    const goToPrev = () => setCurrentImageIndex((prev) => (prev - 1 + images.length) % images.length);

    if (isLoading) {
        return (
            <div className="modal-backdrop" onClick={onClose}>
                <div className="bg-white w-full max-w-3xl mx-auto rounded-xl shadow-2xl p-8 flex items-center justify-center min-h-[300px]" onClick={(e) => e.stopPropagation()}>
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
            <div className="modal-backdrop" onClick={onClose}>
                <div className="bg-white w-full max-w-md mx-auto rounded-xl shadow-2xl p-6 text-center" onClick={(e) => e.stopPropagation()}>
                    <div className="text-red-500 mb-3">
                        <svg className="w-12 h-12 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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

    return (
        <div className="modal-backdrop overflow-y-auto items-start pt-6 pb-8" onClick={onClose}>
            <div className="bg-white w-full max-w-3xl mx-auto rounded-xl shadow-2xl relative overflow-hidden" onClick={(e) => e.stopPropagation()}>
                {/* Close Button */}
                <button
                    onClick={onClose}
                    className="absolute top-3 right-3 z-50 p-2 rounded-full bg-black/40 hover:bg-black/60 text-white transition-all"
                >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                </button>

                {/* Image Carousel */}
                <div className="relative bg-slate-900">
                    {/* Main Image Container - Fixed aspect ratio */}
                    <div className="relative w-full" style={{ paddingBottom: '66.67%' }}> {/* 3:2 aspect ratio */}
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
                                className="absolute left-3 top-1/2 -translate-y-1/2 p-2 rounded-full bg-white/90 hover:bg-white shadow-lg transition-all hover:scale-105"
                            >
                                <svg className="w-5 h-5 text-slate-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 19l-7-7 7-7" />
                                </svg>
                            </button>
                            <button
                                onClick={(e) => { e.stopPropagation(); goToNext(); }}
                                className="absolute right-3 top-1/2 -translate-y-1/2 p-2 rounded-full bg-white/90 hover:bg-white shadow-lg transition-all hover:scale-105"
                            >
                                <svg className="w-5 h-5 text-slate-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
                                </svg>
                            </button>
                        </>
                    )}

                    {/* Image Counter */}
                    {images.length > 1 && (
                        <div className="absolute bottom-3 left-1/2 -translate-x-1/2 bg-black/60 text-white text-sm px-3 py-1 rounded-full">
                            {currentImageIndex + 1} / {images.length}
                        </div>
                    )}

                    {/* Sale/Rent Badge */}
                    <div className="absolute top-3 left-3 bg-white/95 backdrop-blur-sm px-3 py-1 rounded text-xs font-bold uppercase tracking-wide text-slate-800 flex items-center gap-2 shadow">
                        <span className="w-2 h-2 rounded-full bg-red-500"></span>
                        {listing.listing_type === 'sale' ? 'En Venta' : 'En Renta'}
                    </div>
                </div>

                {/* Thumbnail Strip */}
                {images.length > 1 && (
                    <div className="bg-slate-100 p-2 flex gap-1.5 overflow-x-auto">
                        {images.map((img, idx) => (
                            <button
                                key={idx}
                                onClick={() => setCurrentImageIndex(idx)}
                                className={`flex-shrink-0 w-16 h-12 rounded overflow-hidden border-2 transition-all ${idx === currentImageIndex
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

                {/* Content Section */}
                <div className="p-5">
                    <div className="flex flex-col md:flex-row gap-5">
                        {/* Left - Price, Specs, Tags */}
                        <div className="flex-1">
                            {/* Price & Specs Row */}
                            <div className="flex items-center justify-between gap-4 mb-4">
                                <div className="text-3xl font-black text-[#272727] tracking-tight">
                                    {formatPrice(listing.price)}
                                    {listing.listing_type === 'rent' && (
                                        <span className="text-base font-normal text-slate-400 ml-1">/mes</span>
                                    )}
                                </div>

                                {/* Specs */}
                                <div className="flex gap-5 text-center">
                                    {specs.bedrooms && (
                                        <div>
                                            <div className="text-xl font-bold text-[#272727]">{specs.bedrooms}</div>
                                            <div className="text-xs text-slate-500">hab</div>
                                        </div>
                                    )}
                                    {specs.bathrooms && (
                                        <div>
                                            <div className="text-xl font-bold text-[#272727]">{specs.bathrooms}</div>
                                            <div className="text-xs text-slate-500">baños</div>
                                        </div>
                                    )}
                                    {area > 0 && (
                                        <div>
                                            <div className="text-xl font-bold text-[#272727]">{area.toLocaleString()}</div>
                                            <div className="text-xs text-slate-500">m²</div>
                                        </div>
                                    )}
                                </div>
                            </div>

                            {/* Location */}
                            {municipio && (
                                <div className="text-slate-500 text-sm mb-4 flex items-center gap-1.5">
                                    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 16 16">
                                        <path d="M8 16s6-5.686 6-10A6 6 0 0 0 2 6c0 4.314 6 10 6 10zm0-7a3 3 0 1 1 0-6 3 3 0 0 1 0 6z" />
                                    </svg>
                                    {municipio}, El Salvador
                                </div>
                            )}

                            {/* Tags */}
                            {tags.length > 0 && (
                                <div className="flex flex-wrap gap-2 mb-4">
                                    {tags.map((tag, idx) => (
                                        <span
                                            key={idx}
                                            className="bg-slate-100 text-slate-700 text-sm font-medium px-3 py-1 rounded-lg"
                                        >
                                            {tag}
                                        </span>
                                    ))}
                                </div>
                            )}
                        </div>

                        {/* Right - CTA Button */}
                        <div className="md:w-56 shrink-0">
                            <a
                                href={listing.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="w-full bg-blue-600 hover:bg-blue-700 text-white py-3 px-4 rounded-lg font-bold text-center transition-all shadow-md hover:shadow-lg flex items-center justify-center gap-2"
                            >
                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                                </svg>
                                Ver más información
                            </a>
                            <div className="mt-3 text-center text-[10px] text-slate-400 font-medium uppercase tracking-wide">
                                Indexado por <span className="font-black italic text-slate-600">CHIVO<span className="text-blue-600">CASA</span></span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
