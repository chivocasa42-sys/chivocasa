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
    const images = listing.images || [];
    const specs = listing.specs || {};
    const details = listing.details || {};
    const contact = listing.contact_info || {};

    const nextImage = () => {
        setCurrentImage((prev) => (prev + 1) % images.length);
    };

    const prevImage = () => {
        setCurrentImage((prev) => (prev - 1 + images.length) % images.length);
    };

    return (
        <div className="modal-backdrop" onClick={onClose}>
            <div className="modal-content" onClick={(e) => e.stopPropagation()}>
                <div className="modal-header">
                    <h5 className="font-semibold text-lg">{listing.title || 'Listing Details'}</h5>
                    <button
                        onClick={onClose}
                        className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-gray-100"
                    >
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>

                <div className="modal-body">
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        {/* Left column - Images and description */}
                        <div>
                            {/* Image Carousel */}
                            <div className="carousel mb-4 relative">
                                {images.length > 0 ? (
                                    <>
                                        <img
                                            src={images[currentImage]}
                                            alt={`Image ${currentImage + 1}`}
                                            className="w-full h-[350px] object-cover rounded-lg"
                                        />
                                        {images.length > 1 && (
                                            <>
                                                <button
                                                    onClick={prevImage}
                                                    className="carousel-btn prev"
                                                >
                                                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                                                    </svg>
                                                </button>
                                                <button
                                                    onClick={nextImage}
                                                    className="carousel-btn next"
                                                >
                                                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                                                    </svg>
                                                </button>
                                                <div className="absolute bottom-3 left-1/2 transform -translate-x-1/2 bg-black/50 text-white px-2 py-1 rounded text-sm">
                                                    {currentImage + 1} / {images.length}
                                                </div>
                                            </>
                                        )}
                                    </>
                                ) : (
                                    <img
                                        src="https://via.placeholder.com/800x350?text=No+Images"
                                        alt="No images"
                                        className="w-full h-[350px] object-cover rounded-lg"
                                    />
                                )}
                            </div>

                            {/* Description */}
                            <h5 className="font-semibold mb-2">Descripción</h5>
                            <p className="text-muted whitespace-pre-line">
                                {listing.description || 'No description available.'}
                            </p>
                        </div>

                        {/* Right column - Price, specs, contact */}
                        <div>
                            {/* Price */}
                            <div className="mb-4">
                                <h2 className="text-accent text-3xl font-bold mb-2">{formatPrice(listing.price)}</h2>
                                <span className={`inline-block px-2 py-1 rounded text-white text-sm ${listing.listing_type === 'sale' ? 'bg-green-500' : 'bg-blue-500'}`}>
                                    {listing.listing_type === 'sale' ? 'En Venta' : 'En Alquiler'}
                                </span>
                            </div>

                            {/* Specs */}
                            <div className="flex flex-wrap gap-2 mb-4">
                                {specs.bedrooms && (
                                    <span className="spec-badge text-base">
                                        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 16 16">
                                            <path d="M8.354 1.146a.5.5 0 0 0-.708 0l-6 6A.5.5 0 0 0 1.5 7.5v7a.5.5 0 0 0 .5.5h4.5a.5.5 0 0 0 .5-.5v-4h2v4a.5.5 0 0 0 .5.5H14a.5.5 0 0 0 .5-.5v-7a.5.5 0 0 0-.146-.354L13 5.793V2.5a.5.5 0 0 0-.5-.5h-1a.5.5 0 0 0-.5.5v1.293L8.354 1.146z" />
                                        </svg>
                                        {specs.bedrooms} Habitaciones
                                    </span>
                                )}
                                {specs.bathrooms && (
                                    <span className="spec-badge text-base">
                                        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 16 16">
                                            <path d="M7 14s-1 0-1-1 1-4 5-4 5 3 5 4-1 1-1 1H7zm4-6a3 3 0 1 0 0-6 3 3 0 0 0 0 6z" />
                                        </svg>
                                        {specs.bathrooms} Baños
                                    </span>
                                )}
                                {Object.entries(specs)
                                    .filter(([k]) => !['bedrooms', 'bathrooms'].includes(k))
                                    .map(([key, value]) => (
                                        <span key={key} className="spec-badge text-base">
                                            {key}: {value}
                                        </span>
                                    ))
                                }
                            </div>

                            {/* Details */}
                            {Object.keys(details).length > 0 && (
                                <div className="mb-4">
                                    <h6 className="font-semibold mb-2">Detalles</h6>
                                    <ul className="space-y-1">
                                        {Object.entries(details).map(([key, value]) => (
                                            <li key={key}>
                                                <strong>{key}:</strong> {value}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}

                            {/* Contact */}
                            <div className="contact-box">
                                <h6 className="font-semibold mb-3 flex items-center gap-2">
                                    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 16 16">
                                        <path d="M11 6a3 3 0 1 1-6 0 3 3 0 0 1 6 0z" />
                                        <path fillRule="evenodd" d="M0 8a8 8 0 1 1 16 0A8 8 0 0 1 0 8zm8-7a7 7 0 0 0-5.468 11.37C3.242 11.226 4.805 10 8 10s4.757 1.225 5.468 2.37A7 7 0 0 0 8 1z" />
                                    </svg>
                                    Contacto
                                </h6>
                                {contact.nombre && (
                                    <p className="mb-1"><strong>{contact.nombre}</strong></p>
                                )}
                                {contact.telefono && (
                                    <p className="mb-1 flex items-center gap-2">
                                        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 16 16">
                                            <path d="M3.654 1.328a.678.678 0 0 0-1.015-.063L1.605 2.3c-.483.484-.661 1.169-.45 1.77a17.568 17.568 0 0 0 4.168 6.608 17.569 17.569 0 0 0 6.608 4.168c.601.211 1.286.033 1.77-.45l1.034-1.034a.678.678 0 0 0-.063-1.015l-2.307-1.794a.678.678 0 0 0-.58-.122l-2.19.547a1.745 1.745 0 0 1-1.657-.459L5.482 8.062a1.745 1.745 0 0 1-.46-1.657l.548-2.19a.678.678 0 0 0-.122-.58L3.654 1.328zM1.884.511a1.745 1.745 0 0 1 2.612.163L6.29 2.98c.329.423.445.974.315 1.494l-.547 2.19a.678.678 0 0 0 .178.643l2.457 2.457a.678.678 0 0 0 .644.178l2.189-.547a1.745 1.745 0 0 1 1.494.315l2.306 1.794c.829.645.905 1.87.163 2.611l-1.034 1.034c-.74.74-1.846 1.065-2.877.702a18.634 18.634 0 0 1-7.01-4.42 18.634 18.634 0 0 1-4.42-7.009c-.362-1.03-.037-2.137.703-2.877L1.885.511z" />
                                        </svg>
                                        <a href={`tel:${contact.telefono}`} className="text-accent hover:underline">
                                            {contact.telefono}
                                        </a>
                                    </p>
                                )}
                                {contact.whatsapp && (
                                    <p className="mb-1 flex items-center gap-2">
                                        <svg className="w-4 h-4 text-green-500" fill="currentColor" viewBox="0 0 16 16">
                                            <path d="M13.601 2.326A7.854 7.854 0 0 0 7.994 0C3.627 0 .068 3.558.064 7.926c0 1.399.366 2.76 1.057 3.965L0 16l4.204-1.102a7.933 7.933 0 0 0 3.79.965h.004c4.368 0 7.926-3.558 7.93-7.93A7.898 7.898 0 0 0 13.6 2.326zM7.994 14.521a6.573 6.573 0 0 1-3.356-.92l-.24-.144-2.494.654.666-2.433-.156-.251a6.56 6.56 0 0 1-1.007-3.505c0-3.626 2.957-6.584 6.591-6.584a6.56 6.56 0 0 1 4.66 1.931 6.557 6.557 0 0 1 1.928 4.66c-.004 3.639-2.961 6.592-6.592 6.592zm3.615-4.934c-.197-.099-1.17-.578-1.353-.646-.182-.065-.315-.099-.445.099-.133.197-.513.646-.627.775-.114.133-.232.148-.43.05-.197-.1-.836-.308-1.592-.985-.59-.525-.985-1.175-1.103-1.372-.114-.198-.011-.304.088-.403.087-.088.197-.232.296-.346.1-.114.133-.198.198-.33.065-.134.034-.248-.015-.347-.05-.099-.445-1.076-.612-1.47-.16-.389-.323-.335-.445-.34-.114-.007-.247-.007-.38-.007a.729.729 0 0 0-.529.247c-.182.198-.691.677-.691 1.654 0 .977.71 1.916.81 2.049.098.133 1.394 2.132 3.383 2.992.47.205.84.326 1.129.418.475.152.904.129 1.246.08.38-.058 1.171-.48 1.338-.943.164-.464.164-.86.114-.943-.049-.084-.182-.133-.38-.232z" />
                                        </svg>
                                        <a href={`https://wa.me/${contact.whatsapp}`} target="_blank" rel="noopener noreferrer" className="text-green-500 hover:underline">
                                            {contact.whatsapp}
                                        </a>
                                    </p>
                                )}
                                {!contact.nombre && !contact.telefono && !contact.whatsapp && (
                                    <p className="text-muted">No hay información de contacto disponible</p>
                                )}
                            </div>
                        </div>
                    </div>
                </div>

                <div className="modal-footer">
                    <a
                        href={listing.url || '#'}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="btn-accent flex items-center gap-2"
                    >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                        </svg>
                        Ver Original
                    </a>
                </div>
            </div>
        </div>
    );
}
