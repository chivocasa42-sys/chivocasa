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
    const [isExpanded, setIsExpanded] = useState(false);
    const description = listing.description || 'No hay descripción disponible para esta propiedad.';
    const shouldShowReadMore = description.length > 100; // Minimal threshold for read more
    const images = listing.images || [];
    const specs = listing.specs || {};
    const details = listing.details || {};
    const contact = listing.contact_info || {};

    // Get area for price per sqft calc
    const areaStr = specs['Área construida (m²)'] || specs['area'] || specs['m2'] || specs['metros'] || '0';
    const areaVal = parseFloat(String(areaStr).replace(/[^\d.]/g, '')) || 0;
    const pricePerUnit = areaVal > 0 ? listing.price / areaVal : 0;

    // Monthly estimate (simulated 7% APR 30yr)
    const monthlyEst = Math.round((listing.price * 0.00665) + 120);

    return (
        <div className="modal-backdrop overflow-y-auto items-start pt-8 pb-12" onClick={onClose}>
            <div className="bg-white w-full max-w-4xl mx-auto rounded-xl shadow-2xl relative overflow-hidden flex flex-col my-auto" onClick={(e) => e.stopPropagation()}>
                {/* Fixed Top Actions */}
                <div className="absolute top-3 right-3 z-50 flex gap-2">
                    <button className="p-1.5 rounded-lg bg-white/90 hover:bg-white text-slate-700 shadow-sm border border-slate-100 transition-colors" title="Compartir">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 100-2.684 3 3 0 000 2.684zm0 9.316a3 3 0 100-2.684 3 3 0 000 2.684z" />
                        </svg>
                    </button>
                    <button onClick={onClose} className="p-1.5 rounded-lg bg-white/90 hover:bg-white text-slate-700 shadow-sm border border-slate-100 transition-colors" title="Cerrar">
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>

                {/* Mosaico Fotográfico - Estilo Zillow */}
                <div className="grid grid-cols-1 md:grid-cols-4 md:grid-rows-2 h-[240px] lg:h-[320px] gap-0.5 bg-slate-200">
                    <div className="md:col-span-2 md:row-span-2 relative group overflow-hidden bg-slate-100">
                        {images[0] ? (
                            <img src={images[0]} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-700" alt="Vista principal" />
                        ) : (
                            <div className="w-full h-full flex items-center justify-center text-slate-300 text-[10px]">Sin Imagen</div>
                        )}
                        <div className="absolute top-3 left-3 bg-white/95 backdrop-blur px-2 py-0.5 rounded text-[8px] font-black uppercase tracking-widest text-[#272727] flex items-center gap-1 shadow-sm">
                            <span className="w-1.5 h-1.5 rounded-full bg-red-500"></span>
                            {listing.listing_type === 'sale' ? 'EN VENTA' : 'EN ALQUILER'}
                        </div>
                    </div>
                    {/* Fotos secundarias */}
                    {[1, 2, 3, 4].map((i) => (
                        <div key={i} className="hidden md:block relative group overflow-hidden bg-slate-100">
                            {images[i] ? (
                                <img src={images[i]} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-700" alt={`Vista ${i + 1}`} />
                            ) : (
                                <div className="w-full h-full flex items-center justify-center text-slate-200">
                                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                                </div>
                            )}
                            {i === 4 && images.length > 5 && (
                                <div className="absolute inset-0 bg-black/40 flex items-center justify-center">
                                    <button className="bg-white text-slate-900 px-2.5 py-1 rounded font-bold text-[9px] shadow-lg flex items-center gap-1 hover:bg-slate-50 transition-colors">
                                        <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 16 16"><path d="M1 3.5A1.5 1.5 0 0 1 2.5 2h2.764c.758 0 1.46.414 1.828 1.076l.517.924a.5.5 0 0 0 .438.25h4.453A1.5 1.5 0 0 1 14 5.75v6.5A1.5 1.5 0 0 1 12.5 14H2.5A1.5 1.5 0 0 1 1 12.25v-8.75z" /></svg>
                                        Ver {images.length} fotos
                                    </button>
                                </div>
                            )}
                        </div>
                    ))}
                </div>

                {/* Área de Contenido Principal - Máxima Fidelidad Zillow */}
                <div className="flex flex-col lg:flex-row p-4 md:p-5 lg:p-6 gap-6">
                    <div className="flex-1 max-w-xl">
                        {/* Fila de Encabezado: Precio/Dirección vs Specs */}
                        <div className="flex justify-between items-start mb-4 text-[#272727]">
                            <div className="flex-1">
                                <div className="text-[28px] font-black tracking-tighter leading-none mb-1">
                                    {formatPrice(listing.price)}
                                    {listing.listing_type === 'rent' && <span className="text-lg font-normal text-slate-400 ml-1">/mes</span>}
                                </div>
                                <div className="text-slate-700 text-[15px] font-medium leading-tight">
                                    {listing.title}
                                </div>
                            </div>

                            {/* Especificaciones clave (Alineadas a la derecha) */}
                            <div className="flex gap-6 border-slate-100">
                                <div className="text-center">
                                    <div className="text-[22px] font-bold leading-none">{specs.bedrooms || '-'}</div>
                                    <div className="text-[14px] font-normal text-slate-500 lowercase">hab</div>
                                </div>
                                <div className="text-center">
                                    <div className="text-[22px] font-bold leading-none">{specs.bathrooms || '-'}</div>
                                    <div className="text-[14px] font-normal text-slate-500 lowercase border-b border-dotted border-slate-300">baños</div>
                                </div>
                                <div className="text-center">
                                    <div className="text-[22px] font-bold leading-none">{areaVal > 0 ? areaVal.toLocaleString() : '-'}</div>
                                    <div className="text-[14px] font-normal text-slate-500 lowercase">m²</div>
                                </div>
                            </div>
                        </div>

                        {/* Estimación Financiera - Pill Azul Zillow */}
                        <div className="flex items-center gap-2 mb-6">
                            <div className="bg-[#e8f4ff] text-[#006aff] font-bold text-[13px] px-3 py-1.5 rounded-md flex items-center gap-1.5 ">
                                <span className="text-slate-600 font-normal">Est.:</span> {formatPrice(monthlyEst)}/mes
                                <button className="ml-1 text-[#006aff] border-b border-dotted border-[#006aff] hover:text-[#0052cc]">Pre-calificar</button>
                            </div>
                        </div>

                        {/* Cuadrícula de Atributos - Estilo Zillow 6-Box Grid (3 columnas fijos) */}
                        <div className="grid grid-cols-3 gap-2 mb-8">
                            {[
                                {
                                    icon: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />,
                                    value: details['Tipo'] || 'Residencial'
                                },
                                {
                                    icon: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7M18.5 2.5a2.121 2.121 0 113 3L12 15l-4 1 1-4 9.5-9.5z" />,
                                    value: `Año: ${details['Construcción'] || 'N/A'}`
                                },
                                {
                                    icon: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M5 3v18M19 3v18M5 10h14M5 14h14" />,
                                    value: details['Terreno'] || 'Portón/Lote'
                                },
                                {
                                    icon: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />,
                                    value: `Estimado: $--`
                                },
                                {
                                    icon: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />,
                                    value: pricePerUnit > 0 ? `${formatPrice(Math.round(pricePerUnit))}/m²` : 'N/A m²'
                                },
                                {
                                    icon: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />,
                                    value: `$-- Manten.`
                                }
                            ].map((attr, idx) => (
                                <div key={idx} className="bg-[#f8f9fa] p-2 rounded-md border border-slate-50 flex items-center gap-2">
                                    <div className="text-slate-500 shrink-0">
                                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            {attr.icon}
                                        </svg>
                                    </div>
                                    <div className="text-[11px] font-bold text-slate-800 truncate leading-tight">
                                        {attr.value}
                                    </div>
                                </div>
                            ))}
                        </div>

                        {/* Sección de Resumen */}
                        <div className="border-t border-slate-100 pt-5 mb-4">
                            <h3 className="text-base font-black text-[#272727] mb-2">Resumen</h3>
                            <p className={`text-slate-600 leading-normal text-[13px] font-normal mb-1.5 ${isExpanded ? 'whitespace-pre-line' : 'line-clamp-1'}`}>
                                {description}
                            </p>
                            {shouldShowReadMore && (
                                <button onClick={() => setIsExpanded(!isExpanded)} className="text-blue-600 font-bold text-[12px] hover:underline flex items-center gap-1">
                                    {isExpanded ? 'Ver menos' : 'Ver más'}
                                    <svg className={`w-3 h-3 transition-transform ${isExpanded ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" /></svg>
                                </button>
                            )}
                        </div>
                    </div>

                    {/* Acciones del Sidebar (Español) */}
                    <div className="lg:w-64 shrink-0">
                        <div className="bg-white rounded-xl border border-slate-200 shadow-xl overflow-hidden">
                            <div className="p-3.5 border-b border-slate-100 bg-[#fbfcfd]">
                                <h4 className="text-[11px] font-bold text-[#272727] uppercase tracking-wider mb-0.5">Programar visita</h4>
                                <div className="text-[9px] text-slate-500">Respuesta rápida vía WhatsApp</div>
                            </div>
                            <div className="p-3.5 space-y-2">
                                <button
                                    onClick={() => contact.whatsapp ? window.open(`https://wa.me/${contact.whatsapp}`, '_blank') : null}
                                    className="w-full bg-[#006aff] hover:bg-[#0052cc] text-white py-2.5 rounded-lg font-black text-[12px] transition-all shadow-md shadow-blue-100 flex flex-col items-center justify-center leading-none"
                                >
                                    <span>Solicitar recorrido</span>
                                    <span className="text-[8px] font-bold opacity-75 mt-1">lo antes posible</span>
                                </button>
                                <button
                                    onClick={() => contact.telefono ? window.location.href = `tel:${contact.telefono}` : null}
                                    className="w-full bg-white hover:bg-slate-50 text-[#006aff] border-2 border-[#006aff] py-2.5 rounded-lg font-black text-[12px] transition-all"
                                >
                                    Contactar agente
                                </button>
                                <div className="pt-1.5 text-center border-t border-slate-50 mt-2">
                                    <div className="text-[8px] text-slate-400 font-medium uppercase tracking-tighter mb-1">Fuente: {listing.source || 'MLS'}</div>
                                    <div className="text-[9px] text-slate-500 italic">"CHIVOCASA: Índice inteligente"</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
