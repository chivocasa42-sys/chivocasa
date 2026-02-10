'use client';

import type { FilterChip } from '@/hooks/useDepartmentFilters';

interface ActiveFilterChipsProps {
    chips: FilterChip[];
    onRemove: (chipId: string) => void;
    onShowMore?: () => void;
}

const MAX_VISIBLE = 5;

export default function ActiveFilterChips({ chips, onRemove, onShowMore }: ActiveFilterChipsProps) {
    if (chips.length === 0) return null;

    const visible = chips.slice(0, MAX_VISIBLE);
    const hiddenCount = chips.length - MAX_VISIBLE;

    return (
        <div className="active-chips">
            {visible.map((chip) => (
                <span key={chip.id} className="active-chip">
                    <span className="active-chip__label">{chip.label}</span>
                    <button
                        className="active-chip__remove"
                        onClick={() => onRemove(chip.id)}
                        aria-label={`Remover filtro: ${chip.label}`}
                    >
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                            <path d="M18 6L6 18M6 6l12 12" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                    </button>
                </span>
            ))}
            {hiddenCount > 0 && onShowMore && (
                <button className="active-chip active-chip--more" onClick={onShowMore}>
                    +{hiddenCount} más
                </button>
            )}
        </div>
    );
}
