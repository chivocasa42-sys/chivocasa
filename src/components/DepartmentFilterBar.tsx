'use client';

import { useState, useRef, useEffect } from 'react';
import type { FilterType, SortOption } from '@/hooks/useDepartmentFilters';
import PriceRangePopover from './PriceRangePopover';
import FiltersPanel from './FiltersPanel';

interface Municipality {
    municipio_id: number;
    municipio_name: string;
    listing_count: number;
}

interface DepartmentFilterBarProps {
    listingType: FilterType;
    sort: SortOption;
    priceLabel: string;
    priceMin: number | null;
    priceMax: number | null;
    activeFiltersCount: number;
    hasActiveFilters: boolean;
    resultsCount: number;
    municipalities: Municipality[];
    selectedMunicipio: string | null;
    categories: string[];
    onTypeChange: (type: FilterType) => void;
    onSortChange: (sort: SortOption) => void;
    onPriceApply: (min: number | null, max: number | null) => void;
    onPriceClear: () => void;
    onMunicipioSelect: (municipio: string | null) => void;
    onCategoryToggle: (category: string) => void;
    onClearAll: () => void;
}

export default function DepartmentFilterBar({
    listingType,
    sort,
    priceLabel,
    priceMin,
    priceMax,
    activeFiltersCount,
    hasActiveFilters,
    resultsCount,
    municipalities,
    selectedMunicipio,
    categories,
    onTypeChange,
    onSortChange,
    onPriceApply,
    onPriceClear,
    onMunicipioSelect,
    onCategoryToggle,
    onClearAll,
}: DepartmentFilterBarProps) {
    const [showPrice, setShowPrice] = useState(false);
    const [showFilters, setShowFilters] = useState(false);
    const priceRef = useRef<HTMLDivElement>(null);

    // Close price popover on click outside
    useEffect(() => {
        if (!showPrice) return;
        function handleClick(e: MouseEvent) {
            if (priceRef.current && !priceRef.current.contains(e.target as Node)) {
                setShowPrice(false);
            }
        }
        document.addEventListener('mousedown', handleClick);
        return () => document.removeEventListener('mousedown', handleClick);
    }, [showPrice]);

    const sortLabels: Record<SortOption, string> = {
        price_asc: 'Precio \u2191',
        price_desc: 'Precio \u2193',
        recent: 'Recientes',
    };

    return (
        <div className="dept-filter-bar">
            <div className="dept-filter-bar__row">
                {/* Group 1: Segmented + Filtros(N) — mobile row 1 */}
                <div className="dept-filter-bar__row1">
                    <div className="segmented-control">
                        <button
                            className={`segmented-btn ${listingType === 'all' ? 'active' : ''}`}
                            onClick={() => onTypeChange('all')}
                        >
                            Todos
                        </button>
                        <button
                            className={`segmented-btn ${listingType === 'sale' ? 'active' : ''}`}
                            onClick={() => onTypeChange('sale')}
                        >
                            Venta
                        </button>
                        <button
                            className={`segmented-btn ${listingType === 'rent' ? 'active' : ''}`}
                            onClick={() => onTypeChange('rent')}
                        >
                            Renta
                        </button>
                    </div>

                    {/* Filtros (N) — shown in row1 on mobile, inline on desktop */}
                    <button
                        className={`filter-bar-btn dept-filter-bar__filtros-btn ${activeFiltersCount > 0 ? 'filter-bar-btn--active' : ''}`}
                        onClick={() => setShowFilters(true)}
                    >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                            <path d="M22 3H2l8 9.46V19l4 2v-8.54L22 3z" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                        Filtros{activeFiltersCount > 0 ? ` (${activeFiltersCount})` : ''}
                    </button>
                </div>

                <span className="dept-filter-bar__divider" />

                {/* Group 2: Precio + Filtros(N) desktop duplicate — mobile row 2 */}
                <div className="dept-filter-bar__row2">
                    {/* Precio button */}
                    <div className="dept-filter-bar__price-wrapper" ref={priceRef}>
                        <button
                            className={`filter-bar-btn ${priceMin != null || priceMax != null ? 'filter-bar-btn--active' : ''}`}
                            onClick={() => setShowPrice(!showPrice)}
                        >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                                <path d="M12 1v22M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6" strokeLinecap="round" strokeLinejoin="round" />
                            </svg>
                            <span className="filter-bar-btn__label">{priceLabel}</span>
                        </button>
                        {showPrice && (
                            <PriceRangePopover
                                priceMin={priceMin}
                                priceMax={priceMax}
                                onApply={(min: number | null, max: number | null) => {
                                    onPriceApply(min, max);
                                    setShowPrice(false);
                                }}
                                onClear={() => {
                                    onPriceClear();
                                    setShowPrice(false);
                                }}
                                onClose={() => setShowPrice(false)}
                            />
                        )}
                    </div>

                    {/* Filtros (N) — desktop only, hidden on mobile (shown in row1 instead) */}
                    <button
                        className={`filter-bar-btn dept-filter-bar__filtros-desktop ${activeFiltersCount > 0 ? 'filter-bar-btn--active' : ''}`}
                        onClick={() => setShowFilters(true)}
                    >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                            <path d="M22 3H2l8 9.46V19l4 2v-8.54L22 3z" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                        Filtros{activeFiltersCount > 0 ? ` (${activeFiltersCount})` : ''}
                    </button>

                    <span className="dept-filter-bar__divider" />

                    {/* Sort dropdown */}
                    <div className="dropdown-control dept-filter-bar__sort">
                        <select
                            value={sort}
                            onChange={(e) => onSortChange(e.target.value as SortOption)}
                            className="dropdown-select"
                            aria-label="Ordenar por"
                        >
                            <option value="price_asc">Precio: menor a mayor</option>
                            <option value="price_desc">Precio: mayor a menor</option>
                            <option value="recent">Más recientes</option>
                        </select>
                        <div className="dropdown-icon" aria-hidden="true">
                            <svg width="16" height="16" viewBox="0 0 20 20" fill="none">
                                <path d="M6 8l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                            </svg>
                        </div>
                    </div>

                    {/* Sort button — mobile only (replaces long dropdown) */}
                    <button
                        className="filter-bar-btn dept-filter-bar__sort-mobile"
                        onClick={() => {
                            const options: SortOption[] = ['price_asc', 'price_desc', 'recent'];
                            const idx = options.indexOf(sort);
                            onSortChange(options[(idx + 1) % options.length]);
                        }}
                    >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                            <path d="M3 6h18M3 12h12M3 18h6" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                        {sortLabels[sort]}
                    </button>
                </div>

                <span className="dept-filter-bar__divider" />

                {/* Group 3: Results + Clear — mobile row 3 (meta) */}
                <div className="dept-filter-bar__meta">
                    <span className="dept-filter-bar__results">
                        Resultados: <strong>{resultsCount.toLocaleString()}</strong>
                    </span>
                    {hasActiveFilters && (
                        <button
                            className="dept-filter-bar__clear"
                            onClick={onClearAll}
                        >
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                                <path d="M18 6L6 18M6 6l12 12" strokeLinecap="round" strokeLinejoin="round" />
                            </svg>
                            Limpiar
                        </button>
                    )}
                </div>
            </div>

            {/* Filters Panel (overlay / bottomsheet) */}
            {showFilters && (
                <FiltersPanel
                    municipalities={municipalities}
                    selectedMunicipio={selectedMunicipio}
                    onMunicipioSelect={onMunicipioSelect}
                    categories={categories}
                    onCategoryToggle={onCategoryToggle}
                    onClose={() => setShowFilters(false)}
                    onClearAll={onClearAll}
                />
            )}
        </div>
    );
}
