'use client';

import { useState, useEffect, useRef, useCallback } from 'react';

interface SearchResult {
    display_name: string;
    lat: string;
    lon: string;
}

interface HeroSectionProps {
    onLocationSelect?: (lat: number, lng: number, name: string) => void;
}

export default function HeroSection({ onLocationSelect }: HeroSectionProps) {
    const [searchQuery, setSearchQuery] = useState('');
    const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
    const [isSearching, setIsSearching] = useState(false);
    const [selectedIndex, setSelectedIndex] = useState(-1);
    const dropdownRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);
    const searchTimeoutRef = useRef<NodeJS.Timeout | null>(null);

    // Search places using Nominatim (same as MapExplorer)
    const searchPlaces = useCallback(async (query: string) => {
        if (!query.trim() || query.length < 3) {
            setSearchResults([]);
            return;
        }

        setIsSearching(true);
        try {
            const response = await fetch(`/api/geocode?q=${encodeURIComponent(query)}`);

            if (response.ok) {
                const data: SearchResult[] = await response.json();
                setSearchResults(data);
            }
        } catch (err) {
            console.error('Search error:', err);
        } finally {
            setIsSearching(false);
        }
    }, []);

    // Debounced search input
    const handleSearchInput = useCallback((value: string) => {
        setSearchQuery(value);
        setSelectedIndex(-1);

        if (searchTimeoutRef.current) {
            clearTimeout(searchTimeoutRef.current);
        }

        searchTimeoutRef.current = setTimeout(() => {
            searchPlaces(value);
        }, 400);
    }, [searchPlaces]);

    // Close dropdown when clicking outside
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
                setSearchResults([]);
                setSelectedIndex(-1);
            }
        };

        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    const handleSelectResult = (result: SearchResult) => {
        const lat = parseFloat(result.lat);
        const lng = parseFloat(result.lon);
        const name = result.display_name.split(',')[0];

        setSearchQuery(name);
        setSearchResults([]);
        setSelectedIndex(-1);

        // Scroll to map explorer and trigger search there
        if (onLocationSelect) {
            onLocationSelect(lat, lng, name);
        }

        const mapSection = document.getElementById('explorar-mapa');
        if (mapSection) {
            mapSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    };

    // Handle keyboard navigation
    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (searchResults.length === 0) return;

        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                setSelectedIndex(prev =>
                    prev < searchResults.length - 1 ? prev + 1 : prev
                );
                break;
            case 'ArrowUp':
                e.preventDefault();
                setSelectedIndex(prev => prev > 0 ? prev - 1 : -1);
                break;
            case 'Enter':
                e.preventDefault();
                if (selectedIndex >= 0 && selectedIndex < searchResults.length) {
                    handleSelectResult(searchResults[selectedIndex]);
                } else if (searchResults.length > 0) {
                    handleSelectResult(searchResults[0]);
                }
                break;
            case 'Escape':
                setSearchResults([]);
                setSelectedIndex(-1);
                break;
        }
    };

    return (
        <section className="hero-search">
            {/* LCP Image - Preloaded with high priority for Core Web Vitals */}
            <img
                src="/jardin-ca-01.webp"
                alt=""
                aria-hidden="true"
                fetchPriority="high"
                decoding="sync"
                width={1920}
                height={1080}
                className="hero-search-bg"
            />
            <div className="hero-search-overlay" />
            <div className="hero-search-content">
                <h1 className="hero-search-title">
                    Encontrá tu próximo hogar en El Salvador
                </h1>

                <div className="hero-search-form">
                    <div className="hero-search-input-wrapper" ref={dropdownRef}>
                        <input
                            type="text"
                            placeholder="Buscar por ubicación (ej: Santa Tecla, Escalón, San Salvador...)"
                            aria-label="Buscar por ubicación"
                            value={searchQuery}
                            onChange={(e) => handleSearchInput(e.target.value)}
                            onKeyDown={handleKeyDown}
                            ref={inputRef}
                            className="hero-search-input"
                            autoComplete="off"
                        />

                        {isSearching && (
                            <div className="hero-search-loading">
                                <div className="spinner-small"></div>
                            </div>
                        )}

                        {searchResults.length > 0 && (
                            <div className="hero-search-dropdown">
                                {searchResults.map((result, index) => (
                                    <button
                                        key={index}
                                        type="button"
                                        onClick={() => handleSelectResult(result)}
                                        className={`hero-search-dropdown-item${index === selectedIndex ? ' selected' : ''}`}
                                    >
                                        <svg className="w-4 h-4 text-gray-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                                        </svg>
                                        <span className="truncate">{result.display_name}</span>
                                    </button>
                                ))}
                            </div>
                        )}

                    </div>
                </div>

                <p className="hero-search-slogan">
                    Más casa por tu dinero.
                </p>
            </div>
        </section>
    );
}
