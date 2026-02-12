'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import Link from 'next/link';
import Navbar from '@/components/Navbar';

// --- Types ---

interface LocationOption {
    display_name: string;
    lat: string;
    lon: string;
}

interface TopComp {
    title: string;
    price: number;
    area_m2: number;
    price_per_m2: number;
    bedrooms: number | null;
    bathrooms: number | null;
    parking: number | null;
    distance_km: number;
    similarity: number;
    url: string | null;
    active: boolean;
    days_old: number;
}

interface ValuationResult {
    estimated_value: number;
    range_low: number;
    range_high: number;
    confidence: number;
    price_per_m2: number;
    estimated_rent: number | null;
    rent_percentage: number | null;
    projection_12m: number;
    appreciation_rate: number;
    sample_count: number;
    rent_sample_count: number;
    comps_used: number;
    radius_used: number;
    top_comps: TopComp[];
}

interface InsufficientData {
    error: 'insufficient_data';
    message: string;
    sample_count: number;
    radius_used: number;
}

const PROPERTY_TYPES = [
    { value: 'casa', label: 'Casa' },
    { value: 'apartamento', label: 'Apartamento' },
    { value: 'local', label: 'Local' },
    { value: 'lote', label: 'Lote' },
];

function formatCurrency(value: number): string {
    if (value >= 1_000_000) {
        return '$' + (value / 1_000_000).toFixed(1) + 'M';
    }
    return '$' + value.toLocaleString('en-US');
}

function formatCurrencyFull(value: number): string {
    return '$' + value.toLocaleString('en-US');
}

// --- Location Autocomplete (Nominatim via /api/geocode) ---

function LocationAutocomplete({
    value,
    onChange
}: {
    value: LocationOption | null;
    onChange: (location: LocationOption | null) => void;
}) {
    const [query, setQuery] = useState('');
    const [options, setOptions] = useState<LocationOption[]>([]);
    const [isOpen, setIsOpen] = useState(false);
    const [loading, setLoading] = useState(false);
    const inputRef = useRef<HTMLInputElement>(null);
    const dropdownRef = useRef<HTMLDivElement>(null);
    const debounceRef = useRef<NodeJS.Timeout | null>(null);

    useEffect(() => {
        if (value) {
            setQuery(value.display_name.split(',')[0]);
        }
    }, [value]);

    const search = useCallback(async (q: string) => {
        if (q.trim().length < 3) {
            setOptions([]);
            setIsOpen(false);
            return;
        }
        setLoading(true);
        try {
            const res = await fetch(`/api/geocode?q=${encodeURIComponent(q)}`);
            if (res.ok) {
                const data: LocationOption[] = await res.json();
                setOptions(data);
                setIsOpen(data.length > 0);
            }
        } catch {
            setOptions([]);
        } finally {
            setLoading(false);
        }
    }, []);

    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const val = e.target.value;
        setQuery(val);
        onChange(null);
        if (debounceRef.current) clearTimeout(debounceRef.current);
        debounceRef.current = setTimeout(() => search(val), 300);
    };

    const handleSelect = (loc: LocationOption) => {
        onChange(loc);
        setQuery(loc.display_name.split(',')[0]);
        setIsOpen(false);
    };

    useEffect(() => {
        const handleClick = (e: MouseEvent) => {
            if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node) &&
                inputRef.current && !inputRef.current.contains(e.target as Node)) {
                setIsOpen(false);
            }
        };
        document.addEventListener('mousedown', handleClick);
        return () => document.removeEventListener('mousedown', handleClick);
    }, []);

    return (
        <div className="relative">
            <label className="flex items-center gap-1.5 text-sm font-semibold text-slate-700 mb-1.5">
                <svg className="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
                Zona / Colonia
            </label>
            <input
                ref={inputRef}
                type="text"
                value={query}
                onChange={handleInputChange}
                onFocus={() => { if (options.length > 0) setIsOpen(true); }}
                placeholder="Buscar por ubicación (ej: Escalón, Santa Tecla, San Salvador...)"
                className="w-full px-4 py-3 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white"
                autoComplete="off"
            />
            {loading && (
                <div className="absolute right-3 top-[42px]">
                    <div className="w-4 h-4 border-2 border-slate-300 border-t-blue-500 rounded-full animate-spin"></div>
                </div>
            )}
            {isOpen && options.length > 0 && (
                <div
                    ref={dropdownRef}
                    className="absolute z-50 w-full mt-1 bg-white border border-slate-200 rounded-lg shadow-lg max-h-60 overflow-y-auto"
                >
                    {options.map((opt, idx) => {
                        const parts = opt.display_name.split(',');
                        const primary = parts[0]?.trim();
                        const secondary = parts.slice(1, 3).join(',').trim();
                        return (
                            <button
                                key={idx}
                                onClick={() => handleSelect(opt)}
                                className="w-full text-left px-4 py-2.5 hover:bg-blue-50 transition-colors border-b border-slate-50 last:border-0"
                            >
                                <div className="flex items-center gap-2">
                                    <svg className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                                    </svg>
                                    <div>
                                        <div className="font-medium text-sm text-slate-800">{primary}</div>
                                        {secondary && <div className="text-xs text-slate-400">{secondary}</div>}
                                    </div>
                                </div>
                            </button>
                        );
                    })}
                </div>
            )}
        </div>
    );
}

// --- Main Page ---

export default function ValuadorPage() {
    // Form state — pre-filled defaults
    const [selectedLocation, setSelectedLocation] = useState<LocationOption | null>(null);
    const [propertyType, setPropertyType] = useState('casa');
    const [area, setArea] = useState<string>('250');
    const [bedrooms, setBedrooms] = useState<string>('3');
    const [bathrooms, setBathrooms] = useState<string>('2');
    const [parking, setParking] = useState<string>('1');

    // Navbar total listings
    const [totalListings, setTotalListings] = useState(0);
    useEffect(() => {
        fetch('/api/department-stats')
            .then(r => r.ok ? r.json() : [])
            .then((depts: { total_count: number }[]) =>
                setTotalListings(depts.reduce((s, d) => s + d.total_count, 0))
            )
            .catch(() => { });
    }, []);

    // Result state
    const [result, setResult] = useState<ValuationResult | null>(null);
    const [insufficientData, setInsufficientData] = useState<InsufficientData | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const canSubmit = selectedLocation && area && parseFloat(area) > 0;

    const handleSubmit = async () => {
        if (!canSubmit || !selectedLocation) return;

        setLoading(true);
        setError(null);
        setResult(null);
        setInsufficientData(null);

        try {
            const res = await fetch('/api/valuador', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    lat: parseFloat(selectedLocation.lat),
                    lng: parseFloat(selectedLocation.lon),
                    area_m2: parseFloat(area),
                    bedrooms: bedrooms ? parseInt(bedrooms) : null,
                    bathrooms: bathrooms ? parseFloat(bathrooms) : null,
                    parking: parking ? parseInt(parking) : null,
                    property_type: propertyType
                })
            });

            const data = await res.json();

            if (data.error === 'insufficient_data') {
                setInsufficientData(data as InsufficientData);
            } else if (data.error) {
                setError(data.error);
            } else {
                setResult(data as ValuationResult);
            }
        } catch {
            setError('Error de conexión. Intentá de nuevo.');
        } finally {
            setLoading(false);
        }
    };

    // Confidence color
    const getConfidenceColor = (confidence: number) => {
        if (confidence >= 0.6) return 'bg-emerald-500';
        if (confidence >= 0.35) return 'bg-yellow-500';
        return 'bg-red-400';
    };

    return (
        <div className="min-h-screen bg-[var(--bg-body)]">
            <Navbar
                totalListings={totalListings}
                onRefresh={() => window.location.reload()}
            />

            {/* Header */}
            <div className="container mx-auto px-4 max-w-5xl pt-8 pb-4">
                <h1 className="text-3xl md:text-4xl font-black text-[#272727] tracking-tight">
                    Valuador de Inmuebles
                </h1>
                <p className="text-slate-500 mt-1 text-sm md:text-base">
                    Estimá el valor de tu propiedad basado en datos reales del mercado salvadoreño
                </p>
                <p className="text-slate-500 mt-1 text-sm md:text-base">
                    <b>NOTA:</b> Los valores son aproximados, calculados a partir de comparaciones de anuncios disponibles. <b>Esto no sustituye una valoración profesional.</b> Consulte con un experto para una valuación oficial.
                </p>
            </div>

            {/* Main content */}
            <div className="container mx-auto px-4 max-w-5xl pb-16">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-start">
                    {/* Left: Form */}
                    <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
                        <h2 className="text-base font-bold text-slate-800 mb-5 flex items-center gap-2">
                            <svg className="w-5 h-5 text-blue-500" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                            </svg>
                            Datos de la propiedad
                        </h2>

                        <div className="space-y-4">
                            {/* Zona / Colonia */}
                            <LocationAutocomplete
                                value={selectedLocation}
                                onChange={setSelectedLocation}
                            />

                            {/* Property type */}
                            <div>
                                <label className="text-sm font-semibold text-slate-700 mb-1.5 block">
                                    Tipo de propiedad
                                </label>
                                <div className="grid grid-cols-4 gap-2">
                                    {PROPERTY_TYPES.map(pt => (
                                        <button
                                            key={pt.value}
                                            onClick={() => setPropertyType(pt.value)}
                                            className={`px-3 py-2 rounded-lg text-xs font-medium transition-all border ${propertyType === pt.value
                                                ? 'bg-[#1a2b4a] text-white border-[#1a2b4a]'
                                                : 'bg-white text-slate-600 border-slate-200 hover:border-slate-300'
                                                }`}
                                        >
                                            {pt.label}
                                        </button>
                                    ))}
                                </div>
                            </div>

                            {/* Area */}
                            <div>
                                <label className="flex items-center gap-1.5 text-sm font-semibold text-slate-700 mb-1.5">
                                    <svg className="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5v-4m0 4h-4m4 0l-5-5" />
                                    </svg>
                                    Área (m²)
                                </label>
                                <input
                                    type="number"
                                    value={area}
                                    onChange={e => setArea(e.target.value)}
                                    placeholder="250"
                                    min="1"
                                    className="w-full px-4 py-3 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                />
                            </div>

                            {/* Bedrooms + Bathrooms + Parking row */}
                            <div className="grid grid-cols-3 gap-3">
                                <div>
                                    <label className="text-sm font-semibold text-slate-700 mb-1.5 block">
                                        Habitaciones
                                    </label>
                                    <input
                                        type="number"
                                        value={bedrooms}
                                        onChange={e => setBedrooms(e.target.value)}
                                        placeholder="3"
                                        min="0"
                                        className="w-full px-4 py-3 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                    />
                                </div>
                                <div>
                                    <label className="text-sm font-semibold text-slate-700 mb-1.5 block">
                                        Baños
                                    </label>
                                    <input
                                        type="number"
                                        value={bathrooms}
                                        onChange={e => setBathrooms(e.target.value)}
                                        placeholder="2"
                                        min="0"
                                        step="0.5"
                                        className="w-full px-4 py-3 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                    />
                                </div>
                                <div>
                                    <label className="text-sm font-semibold text-slate-700 mb-1.5 block">
                                        Parqueos
                                    </label>
                                    <input
                                        type="number"
                                        value={parking}
                                        onChange={e => setParking(e.target.value)}
                                        placeholder="1"
                                        min="0"
                                        className="w-full px-4 py-3 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                    />
                                </div>
                            </div>

                            {/* Submit */}
                            <button
                                onClick={handleSubmit}
                                disabled={!canSubmit || loading}
                                className="w-full py-3.5 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 disabled:cursor-not-allowed text-white font-bold rounded-lg transition-colors text-sm mt-2"
                            >
                                {loading ? (
                                    <span className="flex items-center justify-center gap-2">
                                        <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                                        Calculando...
                                    </span>
                                ) : (
                                    'Calcular Estimación'
                                )}
                            </button>
                        </div>
                    </div>

                    {/* Right: Results */}
                    <div className="space-y-3">
                        {/* Empty state */}
                        {!result && !insufficientData && !error && !loading && (
                            <div className="bg-white rounded-xl border border-slate-200 p-8 md:p-12 shadow-sm text-center flex flex-col items-center justify-center min-h-[280px]">
                                <svg className="w-14 h-14 text-slate-200 mb-4" fill="none" stroke="currentColor" strokeWidth="1" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                                </svg>
                                <p className="text-slate-400 text-sm max-w-[240px]">
                                    Completá los datos y hacé clic en <strong>Calcular</strong> para ver la estimación
                                </p>
                            </div>
                        )}

                        {/* Loading */}
                        {loading && (
                            <div className="bg-white rounded-xl border border-slate-200 p-12 shadow-sm text-center min-h-[280px] flex flex-col items-center justify-center">
                                <div className="w-8 h-8 border-[3px] border-slate-200 border-t-blue-500 rounded-full animate-spin mb-4"></div>
                                <p className="text-slate-500 text-sm">Analizando propiedades comparables...</p>
                            </div>
                        )}

                        {/* Error */}
                        {error && (
                            <div className="bg-red-50 rounded-xl border border-red-200 p-5">
                                <p className="text-red-600 text-sm font-medium">{error}</p>
                            </div>
                        )}

                        {/* Insufficient data */}
                        {insufficientData && (
                            <div className="bg-amber-50 rounded-xl border border-amber-200 p-5">
                                <p className="text-amber-700 text-sm font-medium">{insufficientData.message}</p>
                                <p className="text-amber-500 text-xs mt-2">
                                    {insufficientData.sample_count} propiedades en {insufficientData.radius_used}km. Se necesitan al menos 3.
                                </p>
                            </div>
                        )}

                        {/* Results */}
                        {result && (
                            <>
                                {/* Main estimate card */}
                                <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
                                    <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-0.5">
                                        Valor Estimado
                                    </div>
                                    <div className="text-3xl sm:text-4xl font-black text-[#272727] tracking-tight">
                                        {formatCurrencyFull(result.estimated_value)}
                                    </div>
                                    <div className="text-xs sm:text-sm text-slate-500 mt-1">
                                        Rango: {formatCurrencyFull(result.range_low)} — {formatCurrencyFull(result.range_high)}
                                    </div>
                                    <div className="mt-3">
                                        <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
                                            <div
                                                className={`h-full rounded-full transition-all duration-700 ${getConfidenceColor(result.confidence)}`}
                                                style={{ width: `${result.confidence * 100}%` }}
                                            ></div>
                                        </div>
                                        <div className="text-[11px] text-slate-400 mt-1">
                                            Confianza: {Math.round(result.confidence * 100)}%
                                            <span className="text-slate-300 ml-1">
                                                · {result.sample_count} comps en {result.radius_used}km
                                            </span>
                                        </div>
                                    </div>
                                </div>

                                {/* Stats cards row */}
                                <div className="grid grid-cols-2 gap-3">
                                    <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
                                        <div className="text-[10px] font-medium text-slate-400 uppercase tracking-wide mb-0.5">Precio/m²</div>
                                        <div className="text-xl sm:text-2xl font-black text-[#272727]">
                                            {formatCurrencyFull(result.price_per_m2)}
                                        </div>
                                        <div className="text-[11px] text-slate-400">promedio zona</div>
                                    </div>
                                    <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
                                        <div className="text-[10px] font-medium text-slate-400 uppercase tracking-wide mb-0.5">Renta Estimada</div>
                                        <div className="text-xl sm:text-2xl font-black text-[#272727]">
                                            {result.estimated_rent ? formatCurrencyFull(result.estimated_rent) : '—'}
                                            <span className="text-xs font-normal text-slate-400">/mes</span>
                                        </div>
                                        <div className="text-[11px] text-slate-400">
                                            {result.rent_percentage != null ? `~${result.rent_percentage}% del valor` : ''}
                                            {result.rent_sample_count >= 3 ? ` · ${result.rent_sample_count} comps` : ' · estimado'}
                                        </div>
                                    </div>
                                </div>

                                {/* 12-month projection */}
                                <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
                                    <div className="flex items-start gap-2.5">
                                        <svg className="w-4 h-4 text-blue-500 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                                        </svg>
                                        <div>
                                            <div className="text-xs font-bold text-slate-700">Proyección a 12 meses</div>
                                            <div className="text-xs text-slate-500 mt-0.5">
                                                Apreciación ~{(result.appreciation_rate * 100).toFixed(1)}% anual → <strong className="text-slate-800">{formatCurrencyFull(result.projection_12m)}</strong>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </>
                        )}
                    </div>
                </div>

                {/* Top 5 Similar Listings Table — full width below */}
                {result && result.top_comps && result.top_comps.length > 0 && (
                    <div className="mt-8">
                        <h3 className="text-base font-bold text-slate-800 mb-3">
                            Propiedades comparables más similares
                        </h3>
                        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
                            {/* Desktop table */}
                            <div className="hidden md:block overflow-x-auto">
                                <table className="w-full text-sm">
                                    <thead>
                                        <tr className="bg-slate-50 border-b border-slate-200">
                                            <th className="text-right px-3 py-2.5 text-xs font-semibold text-slate-500 uppercase tracking-wide">Precio</th>
                                            <th className="text-right px-3 py-2.5 text-xs font-semibold text-slate-500 uppercase tracking-wide">Área</th>
                                            <th className="text-right px-3 py-2.5 text-xs font-semibold text-slate-500 uppercase tracking-wide">$/m²</th>
                                            <th className="text-center px-3 py-2.5 text-xs font-semibold text-slate-500 uppercase tracking-wide">Specs</th>
                                            <th className="text-right px-3 py-2.5 text-xs font-semibold text-slate-500 uppercase tracking-wide">Dist.</th>
                                            <th className="text-right px-3 py-2.5 text-xs font-semibold text-slate-500 uppercase tracking-wide">Similitud</th>
                                            <th className="text-center px-3 py-2.5 text-xs font-semibold text-slate-500 uppercase tracking-wide"></th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {result.top_comps.map((comp, idx) => (
                                            <tr key={idx} className={`border-b border-slate-100 last:border-0 hover:bg-slate-50/50 ${!comp.active ? 'opacity-60' : ''}`}>
                                                <td className="px-3 py-3 text-right font-bold text-slate-700 whitespace-nowrap">
                                                    {formatCurrencyFull(comp.price)}
                                                </td>
                                                <td className="px-3 py-3 text-right text-slate-600 whitespace-nowrap">
                                                    {comp.area_m2} m²
                                                </td>
                                                <td className="px-3 py-3 text-right text-slate-600 whitespace-nowrap">
                                                    ${comp.price_per_m2.toLocaleString()}
                                                </td>
                                                <td className="px-3 py-3 text-center text-xs text-slate-500 whitespace-nowrap">
                                                    {[
                                                        comp.bedrooms != null ? `${comp.bedrooms} hab` : null,
                                                        comp.bathrooms != null ? `${comp.bathrooms} ba` : null,
                                                        comp.parking != null ? `${comp.parking} parq` : null,
                                                    ].filter(Boolean).join(' · ') || '—'}
                                                </td>
                                                <td className="px-3 py-3 text-right text-slate-500 whitespace-nowrap">
                                                    {comp.distance_km}km
                                                </td>
                                                <td className="px-3 py-3 text-right">
                                                    <span className={`inline-block px-2 py-0.5 rounded text-xs font-bold ${comp.similarity >= 70 ? 'bg-emerald-100 text-emerald-700' :
                                                        comp.similarity >= 40 ? 'bg-yellow-100 text-yellow-700' :
                                                            'bg-slate-100 text-slate-500'
                                                        }`}>
                                                        {comp.similarity}%
                                                    </span>
                                                </td>
                                                <td className="px-3 py-3 text-center">
                                                    {comp.active && comp.url ? (
                                                        <a
                                                            href={comp.url}
                                                            target="_blank"
                                                            rel="noopener noreferrer"
                                                            className="text-blue-500 hover:text-blue-700 text-xs font-medium whitespace-nowrap"
                                                        >
                                                            Ver anuncio →
                                                        </a>
                                                    ) : (
                                                        <span className="text-slate-300 text-xs">—</span>
                                                    )}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>

                            {/* Mobile card list */}
                            <div className="md:hidden divide-y divide-slate-100">
                                {result.top_comps.map((comp, idx) => (
                                    <div key={idx} className={`p-4 ${!comp.active ? 'opacity-60' : ''}`}>
                                        <div className="flex items-center justify-between mb-1">
                                            <div className="flex items-center gap-2 text-xs text-slate-500 flex-wrap">
                                                <span className="font-bold text-slate-700">{formatCurrencyFull(comp.price)}</span>
                                                <span>{comp.area_m2} m²</span>
                                                <span>${comp.price_per_m2.toLocaleString()}/m²</span>
                                                <span>{comp.distance_km}km</span>
                                            </div>
                                            <span className={`ml-2 flex-shrink-0 inline-block px-2 py-0.5 rounded text-[10px] font-bold ${comp.similarity >= 70 ? 'bg-emerald-100 text-emerald-700' :
                                                comp.similarity >= 40 ? 'bg-yellow-100 text-yellow-700' :
                                                    'bg-slate-100 text-slate-500'
                                                }`}>
                                                {comp.similarity}%
                                            </span>
                                        </div>
                                        <div className="flex items-center justify-between mt-1">
                                            <div className="text-[11px] text-slate-400">
                                                {[
                                                    comp.bedrooms != null ? `${comp.bedrooms} hab` : null,
                                                    comp.bathrooms != null ? `${comp.bathrooms} baños` : null,
                                                    comp.parking != null ? `${comp.parking} parq` : null,
                                                ].filter(Boolean).join(' · ')}
                                                {!comp.active && ' · inactivo'}
                                            </div>
                                            {comp.active && comp.url ? (
                                                <a
                                                    href={comp.url}
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                    className="text-blue-500 text-[11px] font-medium"
                                                >
                                                    Ver anuncio →
                                                </a>
                                            ) : null}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
