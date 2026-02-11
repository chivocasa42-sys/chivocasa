'use client';

import { useState, useMemo, useCallback } from 'react';

export type FilterType = 'all' | 'sale' | 'rent';
export type SortOption = 'price_asc' | 'price_desc' | 'recent';

export interface DepartmentFilters {
  listingType: FilterType;
  sort: SortOption;
  priceMin: number | null;
  priceMax: number | null;
  municipios: string[];
  categories: string[];
}

export interface FilterChip {
  id: string;
  label: string;
  type: 'municipio' | 'price' | 'category' | 'listingType';
}

interface UseDepartmentFiltersOptions {
  slug: string;
  initialType?: FilterType;
}

const DEFAULTS: DepartmentFilters = {
  listingType: 'all',
  sort: 'price_asc',
  priceMin: null,
  priceMax: null,
  municipios: [],
  categories: [],
};

function formatPriceShort(n: number): string {
  if (n >= 1_000_000) return '$' + (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000) return '$' + Math.round(n / 1_000) + 'K';
  return '$' + n.toLocaleString();
}

export function useDepartmentFilters({ slug, initialType = 'all' }: UseDepartmentFiltersOptions) {
  const [filters, setFilters] = useState<DepartmentFilters>({
    ...DEFAULTS,
    listingType: initialType,
  });

  // --- Actions ---

  const setType = useCallback((type: FilterType) => {
    setFilters(prev => ({ ...prev, listingType: type, priceMin: null, priceMax: null }));
    // Sync URL for SEO without triggering Next.js navigation/remount
    const url = type === 'all' ? `/${slug}` : `/${slug}/${type === 'sale' ? 'venta' : 'renta'}`;
    window.history.replaceState(null, '', url);
  }, [slug]);

  const setSort = useCallback((sort: SortOption) => {
    setFilters(prev => ({ ...prev, sort }));
  }, []);

  const applyPrice = useCallback((min: number | null, max: number | null) => {
    setFilters(prev => ({ ...prev, priceMin: min, priceMax: max }));
  }, []);

  const clearPrice = useCallback(() => {
    setFilters(prev => ({ ...prev, priceMin: null, priceMax: null }));
  }, []);

  const toggleMunicipio = useCallback((municipio: string) => {
    setFilters(prev => {
      const munis = prev.municipios.includes(municipio)
        ? prev.municipios.filter(m => m !== municipio)
        : [...prev.municipios, municipio];
      return { ...prev, municipios: munis };
    });
  }, []);

  const toggleCategory = useCallback((category: string) => {
    setFilters(prev => {
      const cats = prev.categories.includes(category)
        ? prev.categories.filter(c => c !== category)
        : [...prev.categories, category];
      return { ...prev, categories: cats };
    });
  }, []);

  const clearAll = useCallback(() => {
    setFilters(prev => ({
      ...DEFAULTS,
      listingType: prev.listingType, // keep type (URL-driven)
      sort: DEFAULTS.sort,
    }));
  }, []);

  const removeChip = useCallback((chipId: string) => {
    if (chipId === 'price') {
      clearPrice();
    } else if (chipId.startsWith('muni:')) {
      const muni = chipId.slice(5);
      toggleMunicipio(muni);
    } else if (chipId.startsWith('cat:')) {
      const cat = chipId.slice(4);
      toggleCategory(cat);
    }
  }, [clearPrice, toggleMunicipio, toggleCategory]);

  // --- Derived ---

  const activeChips = useMemo<FilterChip[]>(() => {
    const chips: FilterChip[] = [];

    filters.municipios.forEach(muni => {
      chips.push({ id: `muni:${muni}`, label: muni, type: 'municipio' });
    });

    if (filters.priceMin != null || filters.priceMax != null) {
      const minStr = filters.priceMin != null ? formatPriceShort(filters.priceMin) : '$0';
      const maxStr = filters.priceMax != null ? formatPriceShort(filters.priceMax) : '∞';
      chips.push({ id: 'price', label: `${minStr} – ${maxStr}`, type: 'price' });
    }

    filters.categories.forEach(cat => {
      chips.push({ id: `cat:${cat}`, label: cat, type: 'category' });
    });

    return chips;
  }, [filters]);

  const activeFiltersCount = activeChips.length;
  const hasActiveFilters = activeFiltersCount > 0;

  const priceLabel = useMemo(() => {
    if (filters.priceMin != null || filters.priceMax != null) {
      const minStr = filters.priceMin != null ? formatPriceShort(filters.priceMin) : '$0';
      const maxStr = filters.priceMax != null ? formatPriceShort(filters.priceMax) : '∞';
      return `${minStr} – ${maxStr}`;
    }
    return 'Precio';
  }, [filters.priceMin, filters.priceMax]);

  return {
    filters,
    // Actions
    setType,
    setSort,
    applyPrice,
    clearPrice,
    toggleMunicipio,
    toggleCategory,
    removeChip,
    clearAll,
    // Derived
    activeChips,
    activeFiltersCount,
    hasActiveFilters,
    priceLabel,
  };
}
