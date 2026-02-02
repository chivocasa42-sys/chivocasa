'use client';

import { useMemo, useState } from 'react';

interface TagFilterChipsProps {
    /** All listings' tags - will compute popular tags from this */
    allListingTags: (string[] | null)[];
    /** The primary tag of the current page (to exclude from filter chips) */
    primaryTag: string;
    /** Currently selected filter tags */
    selectedTags: string[];
    /** Callback when a tag is toggled */
    onToggleTag: (tag: string) => void;
    /** Maximum number of chips to show initially */
    maxVisible?: number;
}

// El Salvador department names to exclude from filter chips
const DEPARTMENTS = new Set([
    'ahuachapán', 'ahuachapan',
    'cabañas', 'cabanas',
    'chalatenango',
    'cuscatlán', 'cuscatlan',
    'la libertad',
    'la paz',
    'la unión', 'la union',
    'morazán', 'morazan',
    'san miguel',
    'san salvador',
    'san vicente',
    'santa ana',
    'sonsonate',
    'usulután', 'usulutan',
]);

/**
 * TagFilterChips - Displays clickable tag chips for client-side filtering
 * Shows the most popular sub-tags within the current tag page
 * Excludes department names since those are already used as page-level filters
 */
export default function TagFilterChips({
    allListingTags,
    primaryTag,
    selectedTags,
    onToggleTag,
    maxVisible = 5
}: TagFilterChipsProps) {
    const [showAll, setShowAll] = useState(false);

    // Compute popular tags, excluding primary tag and department names
    const popularTags = useMemo(() => {
        const tagCounts: Record<string, number> = {};
        const normalizedPrimary = primaryTag.toLowerCase();

        allListingTags.forEach(tags => {
            if (!tags) return;
            tags.forEach(tag => {
                const normalizedTag = tag.toLowerCase();
                // Exclude the primary page tag
                if (normalizedTag === normalizedPrimary) return;
                // Exclude department names
                if (DEPARTMENTS.has(normalizedTag)) return;
                tagCounts[tag] = (tagCounts[tag] || 0) + 1;
            });
        });

        return Object.entries(tagCounts)
            .map(([tag, count]) => ({ tag, count }))
            .sort((a, b) => b.count - a.count);
    }, [allListingTags, primaryTag]);

    if (popularTags.length === 0) {
        return null;
    }

    const visibleTags = showAll ? popularTags : popularTags.slice(0, maxVisible);
    const hiddenCount = popularTags.length - maxVisible;

    return (
        <div className="tag-filter-section">
            <span className="tag-filter-label">Filtrar por:</span>
            <div className="tag-filter-chips">
                {visibleTags.map(({ tag }) => {
                    const isSelected = selectedTags.includes(tag);
                    return (
                        <button
                            key={tag}
                            onClick={() => onToggleTag(tag)}
                            className={`tag-chip ${isSelected ? 'selected' : ''}`}
                        >
                            {tag}
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
            {selectedTags.length > 0 && (
                <button
                    onClick={() => selectedTags.forEach(t => onToggleTag(t))}
                    className="tag-filter-clear"
                >
                    Limpiar filtros
                </button>
            )}
        </div>
    );
}

