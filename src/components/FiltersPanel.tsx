'use client';

import { createPortal } from 'react-dom';
import { useEffect, useRef, useState, type CSSProperties } from 'react';

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
    const [viewportHeight, setViewportHeight] = useState<number | null>(null);
    const bodyRef = useRef<HTMLDivElement | null>(null);
    const MAX_VISIBLE = 10;

    const visibleMunicipalities = showAllMunicipios
        ? municipalities
        : municipalities.slice(0, MAX_VISIBLE);
    const hiddenCount = municipalities.length - MAX_VISIBLE;

    useEffect(() => {
        const handleKey = (event: KeyboardEvent) => {
            if (event.key === 'Escape') onClose();
        };

        document.addEventListener('keydown', handleKey);
        return () => document.removeEventListener('keydown', handleKey);
    }, [onClose]);

    useEffect(() => {
        const scrollY = window.scrollY;
        const originalBodyOverflow = document.body.style.overflow;
        const originalBodyPosition = document.body.style.position;
        const originalBodyTop = document.body.style.top;
        const originalBodyWidth = document.body.style.width;

        document.body.style.overflow = 'hidden';
        document.body.style.position = 'fixed';
        document.body.style.top = `-${scrollY}px`;
        document.body.style.width = '100%';

        return () => {
            document.body.style.overflow = originalBodyOverflow;
            document.body.style.position = originalBodyPosition;
            document.body.style.top = originalBodyTop;
            document.body.style.width = originalBodyWidth;
            window.scrollTo(0, scrollY);
        };
    }, []);

    useEffect(() => {
        const updateViewportHeight = () => setViewportHeight(window.innerHeight);

        updateViewportHeight();
        window.addEventListener('resize', updateViewportHeight);
        window.addEventListener('orientationchange', updateViewportHeight);

        return () => {
            window.removeEventListener('resize', updateViewportHeight);
            window.removeEventListener('orientationchange', updateViewportHeight);
        };
    }, []);

    useEffect(() => {
        const frame = window.requestAnimationFrame(() => {
            bodyRef.current?.scrollTo({ top: 0, behavior: 'auto' });
        });

        return () => window.cancelAnimationFrame(frame);
    }, []);

    if (typeof document === 'undefined') return null;

    const panelStyle: CSSProperties | undefined = viewportHeight
        ? ({ '--filters-panel-vh': `${viewportHeight}px` } as CSSProperties)
        : undefined;

    return createPortal(
        <div className="filters-panel-backdrop" onClick={onClose}>
            <div
                className="filters-panel"
                style={panelStyle}
                onClick={(event) => event.stopPropagation()}
                role="dialog"
                aria-modal="true"
                aria-label="Filtros avanzados"
            >
                <div className="filters-panel__header">
                    <h3 className="filters-panel__title">
                        <svg
                            width="16"
                            height="16"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            aria-hidden="true"
                        >
                            <path
                                d="M22 3H2l8 9.46V19l4 2v-8.54L22 3z"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                            />
                        </svg>
                        Filtros
                    </h3>
                    <button
                        className="filters-panel__close"
                        onClick={onClose}
                        aria-label="Cerrar"
                    >
                        <svg
                            width="18"
                            height="18"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            aria-hidden="true"
                        >
                            <path
                                d="M18 6L6 18M6 6l12 12"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                            />
                        </svg>
                    </button>
                </div>

                <div ref={bodyRef} className="filters-panel__body">
                    <div className="filters-panel__section">
                        <h4 className="filters-panel__section-title">Ubicación</h4>
                        <div className="tag-filter-chips">
                            {municipalities.length > 0 ? (
                                <>
                                    {visibleMunicipalities.map(
                                        ({
                                            municipio_id,
                                            municipio_name,
                                            listing_count,
                                        }) => {
                                            const isSelected =
                                                selectedMunicipios.includes(
                                                    municipio_name
                                                );

                                            return (
                                                <button
                                                    key={municipio_id}
                                                    onClick={() =>
                                                        onMunicipioToggle(
                                                            municipio_name
                                                        )
                                                    }
                                                    className={`tag-chip ${
                                                        isSelected
                                                            ? 'selected'
                                                            : ''
                                                    }`}
                                                >
                                                    {municipio_name}
                                                    <span className="tag-chip-count">
                                                        ({listing_count})
                                                    </span>
                                                    {isSelected ? (
                                                        <span className="tag-chip-check">
                                                            ✓
                                                        </span>
                                                    ) : null}
                                                </button>
                                            );
                                        }
                                    )}
                                    {!showAllMunicipios && hiddenCount > 0 ? (
                                        <button
                                            onClick={() =>
                                                setShowAllMunicipios(true)
                                            }
                                            className="tag-chip tag-chip-more"
                                        >
                                            +{hiddenCount} más
                                        </button>
                                    ) : null}
                                    {showAllMunicipios && hiddenCount > 0 ? (
                                        <button
                                            onClick={() =>
                                                setShowAllMunicipios(false)
                                            }
                                            className="tag-chip tag-chip-more"
                                        >
                                            Menos
                                        </button>
                                    ) : null}
                                </>
                            ) : (
                                <span className="text-sm text-[var(--text-muted)]">
                                    Sin ubicaciones disponibles
                                </span>
                            )}
                        </div>
                    </div>

                    <div className="filters-panel__section">
                        <h4 className="filters-panel__section-title">Categoría</h4>
                        <div className="tag-filter-chips">
                            {availableCategories.length > 0 ? (
                                availableCategories.map((category) => {
                                    const isSelected =
                                        categories.includes(category);

                                    return (
                                        <button
                                            key={category}
                                            onClick={() =>
                                                onCategoryToggle(category)
                                            }
                                            className={`tag-chip ${
                                                isSelected ? 'selected' : ''
                                            }`}
                                        >
                                            {category}
                                            {isSelected ? (
                                                <span className="tag-chip-check">
                                                    ✓
                                                </span>
                                            ) : null}
                                        </button>
                                    );
                                })
                            ) : (
                                <span className="text-sm text-[var(--text-muted)]">
                                    Sin categorías disponibles
                                </span>
                            )}
                        </div>
                    </div>
                </div>

                <div className="filters-panel__footer">
                    <button
                        className="filters-panel__btn filters-panel__btn--clear"
                        onClick={onClearAll}
                    >
                        Limpiar todo
                    </button>
                    <button
                        className="filters-panel__btn filters-panel__btn--apply"
                        onClick={onClose}
                    >
                        Aplicar
                    </button>
                </div>
            </div>
        </div>,
        document.body
    );
}
