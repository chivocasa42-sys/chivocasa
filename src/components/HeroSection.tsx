'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';

interface Tag {
    tag: string;
}

export default function HeroSection() {
    const router = useRouter();
    const [searchQuery, setSearchQuery] = useState('');
    const [allTags, setAllTags] = useState<Tag[]>([]);
    const [suggestions, setSuggestions] = useState<Tag[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [showDropdown, setShowDropdown] = useState(false);
    const [selectedIndex, setSelectedIndex] = useState(-1);
    const dropdownRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);

    // Preload all tags on mount
    useEffect(() => {
        const fetchAllTags = async () => {
            try {
                const res = await fetch('/api/tags');
                if (res.ok) {
                    const data = await res.json();
                    setAllTags(data.tags || []);
                }
            } catch (error) {
                console.error('Error fetching tags:', error);
            } finally {
                setIsLoading(false);
            }
        };

        fetchAllTags();
    }, []);

    // Filter tags client-side when user types
    useEffect(() => {
        if (searchQuery.trim().length < 2) {
            setSuggestions([]);
            setShowDropdown(false);
            setSelectedIndex(-1);
            return;
        }

        const searchLower = searchQuery.toLowerCase();
        const filtered = allTags
            .filter(t => t.tag.toLowerCase().includes(searchLower))
            .sort((a, b) => {
                // Prioritize tags that start with the search query
                const aStarts = a.tag.toLowerCase().startsWith(searchLower);
                const bStarts = b.tag.toLowerCase().startsWith(searchLower);
                if (aStarts && !bStarts) return -1;
                if (!aStarts && bStarts) return 1;
                return a.tag.localeCompare(b.tag);
            })
            .slice(0, 10);

        setSuggestions(filtered);
        setShowDropdown(filtered.length > 0);
        setSelectedIndex(-1);
    }, [searchQuery, allTags]);

    // Close dropdown when clicking outside
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
                setShowDropdown(false);
                setSelectedIndex(-1);
            }
        };

        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    const handleSelectTag = (tag: string) => {
        // URL encode the tag slug
        const slug = tag.toLowerCase().replace(/\s+/g, '-');
        router.push(`/tag/${encodeURIComponent(slug)}`);
        setShowDropdown(false);
        setSearchQuery('');
        setSelectedIndex(-1);
    };

    // Handle keyboard navigation
    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (!showDropdown || suggestions.length === 0) return;

        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                setSelectedIndex(prev =>
                    prev < suggestions.length - 1 ? prev + 1 : prev
                );
                break;
            case 'ArrowUp':
                e.preventDefault();
                setSelectedIndex(prev => prev > 0 ? prev - 1 : -1);
                break;
            case 'Escape':
                setShowDropdown(false);
                setSelectedIndex(-1);
                break;
        }
    };

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();

        // Only allow selecting from existing suggestions
        if (suggestions.length > 0) {
            // If user has navigated with arrows, use that selection
            if (selectedIndex >= 0 && selectedIndex < suggestions.length) {
                handleSelectTag(suggestions[selectedIndex].tag);
            } else {
                // Otherwise use the first suggestion
                handleSelectTag(suggestions[0].tag);
            }
        }
        // If no suggestions available, do nothing (don't allow arbitrary input)
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
                className="hero-search-bg"
            />
            <div className="hero-search-overlay" />
            <div className="hero-search-content">
                <h1 className="hero-search-title">
                    Inmuebles en El Salvador: compará venta y renta, y pagá lo justo.
                </h1>

                <form onSubmit={handleSubmit} className="hero-search-form">
                    <div className="hero-search-input-wrapper" ref={dropdownRef}>
                        <input
                            type="text"
                            placeholder="Buscar por ubicación (ej: Santa Tecla, San Salvador...)"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            onKeyDown={handleKeyDown}
                            ref={inputRef}
                            className="hero-search-input"
                            autoComplete="off"
                        />

                        {showDropdown && suggestions.length > 0 && (
                            <div className="hero-search-dropdown">
                                {suggestions.map((item, index) => (
                                    <button
                                        key={index}
                                        type="button"
                                        onClick={() => handleSelectTag(item.tag)}
                                        className={`hero-search-dropdown-item${index === selectedIndex ? ' selected' : ''}`}
                                    >
                                        <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                                        </svg>
                                        {item.tag}
                                    </button>
                                ))}
                            </div>
                        )}

                        {!isLoading && searchQuery.trim().length >= 2 && suggestions.length === 0 && (
                            <div className="hero-search-dropdown hero-search-no-results">
                                <span>No se encontraron inmuebles</span>
                            </div>
                        )}

                        {isLoading && (
                            <div className="hero-search-loading">
                                <div className="spinner-small"></div>
                            </div>
                        )}
                    </div>
                </form>

                <p className="hero-search-slogan">
                    Más casa por tu dinero.
                </p>
            </div>
        </section>
    );
}
