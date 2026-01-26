'use client';

import { useState } from 'react';
import { Listing } from '@/types/listing';

interface ListingModalProps {
    listing: Listing;
    onClose: () => void;
}

function formatPrice(price: number): string {
    if (!price) return 'N/A';
    return '$' + price.toLocaleString('en-US');
}

export default function ListingModal({ listing, onClose }: ListingModalProps) {
    const [currentImage, setCurrentImage] = useState(0);
    const [isExpanded, setIsExpanded] = useState(false);
    const images = listing.images || [];
    const specs = listing.specs || {};
    const details = listing.details || {};
    const contact = listing.contact_info || {};

    const description = listing.description || 'No hay descripción disponible para esta propiedad.';
    const shouldShowReadMore = description.length > 200;
    const displayText = isExpanded ? description : (shouldShowReadMore ? `${description.slice(0, 200)}...` : description);

    const nextImage = (e: React.MouseEvent) => {
        e.stopPropagation();
        setCurrentImage((prev) => (prev + 1) % images.length);
    };

    const prevImage = (e: React.MouseEvent) => {
        e.stopPropagation();
        setCurrentImage((prev) => (prev - 1 + images.length) % images.length);
    };

    return (
        <div className="modal-backdrop" onClick={onClose}>
            <div className="modal-content-premium" onClick={(e) => e.stopPropagation()}>
                {/* Close Button */}
                <button
                    onClick={onClose}
                    className="modal-close-btn"
                    aria-label="Cerrar"
                >
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                </button>

                <div className="flex-1 overflow-y-auto">
                    <div className="grid grid-cols-1 lg:grid-cols-2">
                        {/* Left column - Images */}
                        <div className="relative bg-slate-900 h-[350px] lg:h-[500px]">
                            {images.length > 0 ? (
                                <>
                                    <img
                                        src={images[currentImage]}
                                        alt={listing.title}
                                        className="w-full h-full object-cover"
                                    />
                                    {images.length > 1 && (
                                        <>
                                            <div className="absolute inset-0 flex items-center justify-between px-4 pointer-events-none">
                                                <button
                                                    onClick={prevImage}
                                                    className="carousel-btn-premium pointer-events-auto"
                                                >
                                                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                                                    </svg>
                                                </button>
                                                <button
                                                    onClick={nextImage}
                                                    className="carousel-btn-premium pointer-events-auto"
                                                >
                                                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                                                    </svg>
                                                </button>
                                            </div>
                                            <div className="absolute bottom-6 left-1/2 transform -translate-x-1/2 bg-black/40 backdrop-blur-md text-white px-3 py-1.5 rounded-full text-xs font-semibold tracking-wider">
                                                {currentImage + 1} / {images.length}
                                            </div>
                                        </>
                                    )}
                                </>
                            ) : (
                                <div className="w-full h-full flex items-center justify-center bg-slate-100 text-slate-400">
                                    <svg className="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                                    </svg>
                                </div>
                            )}
                        </div>

                        {/* Right column - Data */}
                        <div className="p-8 lg:p-12 overflow-y-auto bg-white">
                            {/* Header Info */}
                            <div className="mb-8">
                                <div className="flex items-center gap-2 mb-4">
                                    <span className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-widest text-white shadow-sm ${listing.listing_type === 'sale' ? 'bg-emerald-500' : 'bg-blue-500'}`}>
                                        {listing.listing_type === 'sale' ? 'En Venta' : 'En Alquiler'}
                                    </span>
                                    {typeof listing.location === 'string' && (
                                        <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                                            {listing.location as string}
                                        </span>
                                    )}
                                </div>
                                <h1 className="text-3xl font-bold text-slate-900 leading-tight mb-2">
                                    {listing.title}
                                </h1>
                                <div className="text-4xl font-extrabold text-[var(--primary)] tracking-tight">
                                    {formatPrice(listing.price)}
                                </div>
                            </div>

                            {/* Key Specs */}
                            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-10">
                                {specs.bedrooms && (
                                    <div className="spec-badge-premium">
                                        <svg className="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
                                        </svg>
                                        <span>{specs.bedrooms} Hab.</span>
                                    </div>
                                )}
                                {specs.bathrooms && (
                                    <div className="spec-badge-premium">
                                        <svg className="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 14v.01M12 14v.01M16 14v.01M21 12c0 1.657-3.582 3-8 3s-8-1.343-8-3 3.582-3 8-3 8 1.343 8 3zM3 20h18M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
                                        </svg>
                                        <span>{specs.bathrooms} Baños</span>
                                    </div>
                                )}
                                {Object.entries(specs)
                                    .filter(([k]) => !['bedrooms', 'bathrooms'].includes(k))
                                    .slice(0, 1)
                                    .map(([key, value]) => (
                                        <div key={key} className="spec-badge-premium">
                                            <svg className="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
                                            </svg>
                                            <span>{value}</span>
                                        </div>
                                    ))
                                }
                            </div>

                            {/* Description */}
                            <div className="mb-10">
                                <h3 className="text-sm font-bold uppercase tracking-widest text-slate-400 mb-4">Descripción</h3>
                                <p className="text-slate-600 leading-relaxed whitespace-pre-line text-lg">
                                    {displayText}
                                </p>
                                {shouldShowReadMore && (
                                    <button
                                        onClick={() => setIsExpanded(!isExpanded)}
                                        className="mt-2 text-sm font-bold text-[var(--primary)] hover:underline flex items-center gap-1"
                                    >
                                        {isExpanded ? 'Ver menos' : 'Ver más'}
                                        <svg
                                            className={`w-4 h-4 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                                            fill="none"
                                            stroke="currentColor"
                                            viewBox="0 0 24 24"
                                        >
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                        </svg>
                                    </button>
                                )}
                            </div>

                            {/* Details Table */}
                            {Object.keys(details).length > 0 && (
                                <div className="mb-10">
                                    <h3 className="text-sm font-bold uppercase tracking-widest text-slate-400 mb-4">Detalles Adicionales</h3>
                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-y-3 gap-x-8">
                                        {Object.entries(details).map(([key, value]) => (
                                            <div key={key} className="flex justify-between py-2 border-b border-slate-100">
                                                <span className="text-slate-500 font-medium">{key}</span>
                                                <span className="text-slate-900 font-bold text-right pl-4">{value}</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Contact Card */}
                            <div className="contact-card-premium">
                                <h3 className="text-base font-bold text-slate-900 mb-6 flex items-center gap-2">
                                    <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                                    Información de Contacto
                                </h3>

                                <div className="space-y-4">
                                    {contact.nombre && (
                                        <div className="flex items-center gap-4">
                                            <div className="w-10 h-10 rounded-full bg-slate-200 flex items-center justify-center font-bold text-slate-600">
                                                {contact.nombre[0]}
                                            </div>
                                            <div>
                                                <div className="text-xs text-slate-400 font-bold uppercase tracking-wider">Publicado por</div>
                                                <div className="text-lg font-bold text-slate-900">{contact.nombre}</div>
                                            </div>
                                        </div>
                                    )}

                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-6">
                                        {contact.telefono && (
                                            <a
                                                href={`tel:${contact.telefono}`}
                                                className="flex items-center justify-center gap-2 py-3 px-4 bg-white border border-slate-200 rounded-xl font-bold text-slate-700 hover:border-[var(--primary)] hover:text-[var(--primary)] transition-all flex-1"
                                            >
                                                <svg className="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
                                                </svg>
                                                Llamar
                                            </a>
                                        )}
                                        {contact.whatsapp && (
                                            <a
                                                href={`https://wa.me/${contact.whatsapp}`}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="flex items-center justify-center gap-2 py-3 px-4 bg-emerald-50 border border-emerald-100 rounded-xl font-bold text-emerald-700 hover:bg-emerald-100 transition-all flex-1"
                                            >
                                                <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                                                    <path d="M12.012 2c-5.518 0-9.997 4.48-9.997 9.998 0 1.763.459 3.484 1.33 5.004L2 22l5.122-1.343c1.48.807 3.138 1.233 4.832 1.233 5.518 0 10-4.482 10-10.001 0-5.517-4.481-9.998-10-9.998zm-4.706 14.502l-.338-.201c-1.353-.807-2.193-2.184-2.193-3.693 0-2.316 1.884-4.2 4.2-4.2s4.2 1.884 4.2 4.2-1.884 4.2-4.2 4.2c-.687 0-1.359-.166-1.956-.479l-.317-.167L5.805 16.9l1.501-.398z" />
                                                </svg>
                                                WhatsApp
                                            </a>
                                        )}
                                    </div>
                                </div>
                            </div>

                            {/* External Link */}
                            <div className="mt-8 pt-8 border-t border-slate-100 flex justify-center">
                                <a
                                    href={listing.url || '#'}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="flex items-center gap-2 text-sm font-bold text-slate-400 hover:text-[var(--primary)] transition-all uppercase tracking-widest"
                                >
                                    Ver fuente original
                                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                                    </svg>
                                </a>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
