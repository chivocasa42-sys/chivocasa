'use client';

import { useState, useEffect, useCallback } from 'react';

interface PriceRangePopoverProps {
    priceMin: number | null;
    priceMax: number | null;
    onApply: (min: number | null, max: number | null) => void;
    onClear: () => void;
    onClose: () => void;
}

const SLIDER_MIN = 0;
const SLIDER_MAX = 1_000_000;
const SLIDER_STEP = 5_000;

const PRESETS = [
    { label: '< $100K', min: null, max: 100_000 },
    { label: '$100K – $250K', min: 100_000, max: 250_000 },
    { label: '$250K – $500K', min: 250_000, max: 500_000 },
    { label: '> $500K', min: 500_000, max: null },
];

function formatInput(value: number | null): string {
    if (value == null) return '';
    return value.toLocaleString('en-US');
}

function parseInput(value: string): number | null {
    const cleaned = value.replace(/[^0-9]/g, '');
    if (!cleaned) return null;
    return parseInt(cleaned, 10);
}

export default function PriceRangePopover({
    priceMin,
    priceMax,
    onApply,
    onClear,
    onClose,
}: PriceRangePopoverProps) {
    const [localMin, setLocalMin] = useState<number | null>(priceMin);
    const [localMax, setLocalMax] = useState<number | null>(priceMax);
    const [minInput, setMinInput] = useState(formatInput(priceMin));
    const [maxInput, setMaxInput] = useState(formatInput(priceMax));

    // Sync local state when external props change
    useEffect(() => {
        setLocalMin(priceMin);
        setLocalMax(priceMax);
        setMinInput(formatInput(priceMin));
        setMaxInput(formatInput(priceMax));
    }, [priceMin, priceMax]);

    const handleMinInput = useCallback((val: string) => {
        setMinInput(val);
        setLocalMin(parseInput(val));
    }, []);

    const handleMaxInput = useCallback((val: string) => {
        setMaxInput(val);
        setLocalMax(parseInput(val));
    }, []);

    const handleSliderMin = useCallback((val: number) => {
        setLocalMin(val === SLIDER_MIN ? null : val);
        setMinInput(val === SLIDER_MIN ? '' : val.toLocaleString('en-US'));
    }, []);

    const handleSliderMax = useCallback((val: number) => {
        setLocalMax(val === SLIDER_MAX ? null : val);
        setMaxInput(val === SLIDER_MAX ? '' : val.toLocaleString('en-US'));
    }, []);

    const handlePreset = useCallback((min: number | null, max: number | null) => {
        setLocalMin(min);
        setLocalMax(max);
        setMinInput(formatInput(min));
        setMaxInput(formatInput(max));
    }, []);

    const handleApply = () => {
        onApply(localMin, localMax);
    };

    const handleClear = () => {
        setLocalMin(null);
        setLocalMax(null);
        setMinInput('');
        setMaxInput('');
        onClear();
    };

    // Escape key closes
    useEffect(() => {
        const handleKey = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onClose();
        };
        document.addEventListener('keydown', handleKey);
        return () => document.removeEventListener('keydown', handleKey);
    }, [onClose]);

    const sliderMinVal = localMin ?? SLIDER_MIN;
    const sliderMaxVal = localMax ?? SLIDER_MAX;

    return (
        <div className="price-popover">
            <div className="price-popover__header">
                <h3 className="price-popover__title">Rango de precio</h3>
                <button className="price-popover__close" onClick={onClose} aria-label="Cerrar">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M18 6L6 18M6 6l12 12" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                </button>
            </div>

            {/* Inputs */}
            <div className="price-popover__inputs">
                <div className="price-popover__field">
                    <label className="price-popover__label">Mínimo</label>
                    <div className="price-popover__input-wrap">
                        <span className="price-popover__prefix">$</span>
                        <input
                            type="text"
                            inputMode="numeric"
                            value={minInput}
                            onChange={(e) => handleMinInput(e.target.value)}
                            placeholder="0"
                            className="price-popover__input"
                        />
                    </div>
                </div>
                <span className="price-popover__separator">–</span>
                <div className="price-popover__field">
                    <label className="price-popover__label">Máximo</label>
                    <div className="price-popover__input-wrap">
                        <span className="price-popover__prefix">$</span>
                        <input
                            type="text"
                            inputMode="numeric"
                            value={maxInput}
                            onChange={(e) => handleMaxInput(e.target.value)}
                            placeholder="Sin límite"
                            className="price-popover__input"
                        />
                    </div>
                </div>
            </div>

            {/* Dual-thumb slider */}
            <div className="price-slider">
                <div className="price-slider__track">
                    <div
                        className="price-slider__range"
                        style={{
                            left: `${(sliderMinVal / SLIDER_MAX) * 100}%`,
                            right: `${100 - (sliderMaxVal / SLIDER_MAX) * 100}%`,
                        }}
                    />
                </div>
                <input
                    type="range"
                    min={SLIDER_MIN}
                    max={SLIDER_MAX}
                    step={SLIDER_STEP}
                    value={sliderMinVal}
                    onChange={(e) => {
                        const v = parseInt(e.target.value);
                        if (v <= sliderMaxVal - SLIDER_STEP) handleSliderMin(v);
                    }}
                    className="price-slider__thumb price-slider__thumb--min"
                />
                <input
                    type="range"
                    min={SLIDER_MIN}
                    max={SLIDER_MAX}
                    step={SLIDER_STEP}
                    value={sliderMaxVal}
                    onChange={(e) => {
                        const v = parseInt(e.target.value);
                        if (v >= sliderMinVal + SLIDER_STEP) handleSliderMax(v);
                    }}
                    className="price-slider__thumb price-slider__thumb--max"
                />
            </div>

            {/* Presets */}
            <div className="price-popover__presets">
                {PRESETS.map((p) => (
                    <button
                        key={p.label}
                        className={`price-popover__preset ${
                            localMin === p.min && localMax === p.max ? 'price-popover__preset--active' : ''
                        }`}
                        onClick={() => handlePreset(p.min, p.max)}
                    >
                        {p.label}
                    </button>
                ))}
            </div>

            {/* Actions */}
            <div className="price-popover__actions">
                <button className="price-popover__btn price-popover__btn--clear" onClick={handleClear}>
                    Limpiar
                </button>
                <button className="price-popover__btn price-popover__btn--apply" onClick={handleApply}>
                    Aplicar
                </button>
            </div>
        </div>
    );
}
