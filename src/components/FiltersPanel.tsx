'use client';

import { useEffect, useState } from 'react';

interface Municipality {
    municipio_id: number;
    municipio_name: string;
    listing_count: number;
}

interface FiltersPanelProps {
    municipalities: Municipality[];
    selectedMunicipios: string[];
    onMunicipioToggle: (municipio: string) => void;
    availableCategories: string[];
    categories: string[];
    onCategoryToggle: (category: string) => void;
    onClose: () => void;
    onClearAll: () => void;
}

export default function FiltersPanel({
    municipalities,
    selectedMunicipios,
    onMunicipioToggle,
    availableCategories,
    categories,
    onCategoryToggle,
    onClose,
    onClearAll,
}: FiltersPanelProps) {
    const [showAllMunicipios, setShowAllMunicipios] = useState(false);
    const MAX_VISIBLE = 10;

    const visibleMunicipalities = showAllMunicipios
        ? municipalities
        : municipalities.slice(0, MAX_VISIBLE);
    const hiddenCount = municipalities.length - MAX_VISIBLE;

    // Escape key closes
    useEffect(() => {
        const handleKey = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onClose();
        };
        document.addEventListener('keydown', handleKey);
        return () => document.removeEventListener('keydown', handleKey);
    }, [onClose]);

    // Prevent body scroll when panel is open
    useEffect(() => {
        document.body.style.overflow = 'hidden';
        return () => { document.body.style.overflow = ''; };
    }, []);

    return (
        <div className="filters-panel-backdrop" onClick={onClose}>
            <div
                className="filters-panel"
                onClick={(e) => e.stopPropagation()}
                role="dialog"
                aria-modal="true"
                aria-label="Filtros avanzados"
            >
                {/* Header */}
                <div className="filters-panel__header">
                    <h3 className="filters-panel__title">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                            <path d="M22 3H2l8 9.46V19l4 2v-8.54L22 3z" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                        Filtros
                    </h3>
                    <button className="filters-panel__close" onClick={onClose} aria-label="Cerrar">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M18 6L6 18M6 6l12 12" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                    </button>
                </div>

                {/* Body */}
                <div className="filters-panel__body">
                    {/* Ubicación — always visible (static) */}
                    <div className="filters-panel__section">
                        <h4 className="filters-panel__section-title">Ubicación</h4>
                        <div className="tag-filter-chips">
                            {municipalities.length > 0 ? (
                                <>
                                    {visibleMunicipalities.map(({ municipio_id, municipio_name, listing_count }) => {
                                        const isSelected = selectedMunicipios.includes(municipio_name);
                                        return (
                                            <button
                                                key={municipio_id}
                                                onClick={() => onMunicipioToggle(municipio_name)}
                                                className={`tag-chip ${isSelected ? 'selected' : ''}`}
                                            >
                                                {municipio_name}
                                                <span className="tag-chip-count">({listing_count})</span>
                                                {isSelected && <span className="tag-chip-check">✓</span>}
                                            </button>
                                        );
                                    })}
                                    {!showAllMunicipios && hiddenCount > 0 && (
                                        <button
                                            onClick={() => setShowAllMunicipios(true)}
                                            className="tag-chip tag-chip-more"
                                        >
                                            +{hiddenCount} más
                                        </button>
                                    )}
                                    {showAllMunicipios && hiddenCount > 0 && (
                                        <button
                                            onClick={() => setShowAllMunicipios(false)}
                                            className="tag-chip tag-chip-more"
                                        >
                                            Menos
                                        </button>
                                    )}
                                </>
                            ) : (
                                <span className="text-sm text-[var(--text-muted)]">Sin ubicaciones disponibles</span>
                            )}
                        </div>
                    </div>

                    {/* Categorías — dynamic from tags */}
                    <div className="filters-panel__section">
                        <h4 className="filters-panel__section-title">Categoría</h4>
                        <div className="tag-filter-chips">
                            {availableCategories.length > 0 ? (
                                availableCategories.map((cat) => {
                                    const isSelected = categories.includes(cat);
                                    return (
                                        <button
                                            key={cat}
                                            onClick={() => onCategoryToggle(cat)}
                                            className={`tag-chip ${isSelected ? 'selected' : ''}`}
                                        >
                                            {cat}
                                            {isSelected && <span className="tag-chip-check">✓</span>}
                                        </button>
                                    );
                                })
                            ) : (
                                <span className="text-sm text-[var(--text-muted)]">Sin categorías disponibles</span>
                            )}
                        </div>
                    </div>
                </div>

                {/* Footer */}
                <div className="filters-panel__footer">
                    <button className="filters-panel__btn filters-panel__btn--clear" onClick={onClearAll}>
                        Limpiar todo
                    </button>
                    <button className="filters-panel__btn filters-panel__btn--apply" onClick={onClose}>
                        Aplicar
                    </button>
                </div>
            </div>
        </div>
    );
}
