'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';

interface Tag {
    tag: string;
}

export default function HeroSection() {
    const router = useRouter();
    const [searchQuery, setSearchQuery] = useState('');
    const [suggestions, setSuggestions] = useState<Tag[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [showDropdown, setShowDropdown] = useState(false);
    const dropdownRef = useRef<HTMLDivElement>(null);

    // Fetch suggestions when user types
    useEffect(() => {
        const fetchSuggestions = async () => {
            if (searchQuery.trim().length < 2) {
                setSuggestions([]);
                setShowDropdown(false);
                return;
            }

            setIsLoading(true);
            try {
                const res = await fetch(`/api/tags?query=${encodeURIComponent(searchQuery)}`);
                if (res.ok) {
                    const data = await res.json();
                    setSuggestions(data.tags || []);
                    setShowDropdown(data.tags.length > 0);
                }
            } catch (error) {
                console.error('Error fetching tags:', error);
            } finally {
                setIsLoading(false);
            }
        };

        const debounce = setTimeout(fetchSuggestions, 300);
        return () => clearTimeout(debounce);
    }, [searchQuery]);

    // Close dropdown when clicking outside
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
                setShowDropdown(false);
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
    };

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();

        // If there are suggestions, use the first one
        if (suggestions.length > 0) {
            handleSelectTag(suggestions[0].tag);
        }
        // Otherwise, if user typed something, search for it anyway
        else if (searchQuery.trim().length > 0) {
            handleSelectTag(searchQuery.trim());
        }
    };

    return (
        <section className="hero-search">
            <div className="hero-search-overlay" />
            <div className="hero-search-content">
                <h1 className="hero-search-title">
                    Más casa por tu dinero.
                </h1>

                <form onSubmit={handleSubmit} className="hero-search-form">
                    <div className="hero-search-input-wrapper" ref={dropdownRef}>
                        <input
                            type="text"
                            placeholder="Buscar por ubicación (ej: Santa Tecla, San Salvador...)"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="hero-search-input"
                        />

                        {showDropdown && suggestions.length > 0 && (
                            <div className="hero-search-dropdown">
                                {suggestions.map((item, index) => (
                                    <button
                                        key={index}
                                        type="button"
                                        onClick={() => handleSelectTag(item.tag)}
                                        className="hero-search-dropdown-item"
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

                        {isLoading && (
                            <div className="hero-search-loading">
                                <div className="spinner-small"></div>
                            </div>
                        )}
                    </div>
                </form>
            </div>
        </section>
    );
}
