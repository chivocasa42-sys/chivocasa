'use client';

import { useState } from 'react';

interface Municipality {
    municipio_id: number;
    municipio_name: string;
    listing_count: number;
}

interface MunicipalityFilterChipsProps {
    /** Available municipalities for the current department */
    municipalities: Municipality[];
    /** Currently selected municipality name (null = all) */
    selectedMunicipio: string | null;
    /** Callback when a municipality is selected/deselected */
    onSelect: (municipio: string | null) => void;
    /** Maximum chips to show initially */
    maxVisible?: number;
}

/**
 * MunicipalityFilterChips - Displays clickable municipality chips for server-side filtering
 * Shows municipalities (L3) within a department with listing counts
 */
export default function MunicipalityFilterChips({
    municipalities,
    selectedMunicipio,
    onSelect,
    maxVisible = 8
}: MunicipalityFilterChipsProps) {
    const [showAll, setShowAll] = useState(false);

    if (municipalities.length === 0) {
        return null;
    }

    const visibleMunicipalities = showAll ? municipalities : municipalities.slice(0, maxVisible);
    const hiddenCount = municipalities.length - maxVisible;

    return (
        <div>
            <div className="control-label mb-2">Ubicación</div>
            <div className="tag-filter-chips">
                {visibleMunicipalities.map(({ municipio_id, municipio_name, listing_count }) => {
                    const isSelected = selectedMunicipio === municipio_name;
                    return (
                        <button
                            key={municipio_id}
                            onClick={() => onSelect(isSelected ? null : municipio_name)}
                            className={`tag-chip ${isSelected ? 'selected' : ''}`}
                        >
                            {municipio_name}
                            <span className="tag-chip-count">({listing_count})</span>
                            {isSelected && (
                                <span className="tag-chip-check">✓</span>
                            )}
                        </button>
                    );
                })}
                {!showAll && hiddenCount > 0 && (
                    <button
                        onClick={() => setShowAll(true)}
                        className="tag-chip tag-chip-more"
                    >
                        +{hiddenCount} más
                    </button>
                )}
                {showAll && hiddenCount > 0 && (
                    <button
                        onClick={() => setShowAll(false)}
                        className="tag-chip tag-chip-more"
                    >
                        Menos
                    </button>
                )}
            </div>
        </div>
    );
}
