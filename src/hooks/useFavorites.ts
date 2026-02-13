'use client';

import { useState, useCallback, useEffect } from 'react';

const COOKIE_NAME = 'sivarcasas_favorites';
const COOKIE_MAX_AGE = 60 * 60 * 24 * 365; // 1 year

/** Read the favorites cookie and return the set of external_id strings. */
function readCookie(): Set<string> {
    if (typeof document === 'undefined') return new Set();
    const match = document.cookie
        .split('; ')
        .find(row => row.startsWith(`${COOKIE_NAME}=`));
    if (!match) return new Set();
    try {
        const decoded = decodeURIComponent(match.split('=')[1]);
        const ids: string[] = JSON.parse(decoded);
        return new Set(ids);
    } catch {
        return new Set();
    }
}

/** Write the favorites set back to the cookie. */
function writeCookie(ids: Set<string>): void {
    const value = encodeURIComponent(JSON.stringify([...ids]));
    document.cookie = `${COOKIE_NAME}=${value}; path=/; max-age=${COOKIE_MAX_AGE}; SameSite=Lax`;
}

/**
 * Hook to manage favorite listings via cookies.
 * Stores external_id values as strings to avoid precision issues with large numbers.
 */
export function useFavorites() {
    const [favorites, setFavorites] = useState<Set<string>>(new Set());

    // Hydrate from cookie on mount
    useEffect(() => {
        setFavorites(readCookie());
    }, []);

    const isFavorite = useCallback(
        (externalId: string | number) => favorites.has(String(externalId)),
        [favorites]
    );

    const toggleFavorite = useCallback((externalId: string | number) => {
        setFavorites(prev => {
            const next = new Set(prev);
            const key = String(externalId);
            if (next.has(key)) {
                next.delete(key);
            } else {
                next.add(key);
            }
            writeCookie(next);
            return next;
        });
    }, []);

    const addFavorite = useCallback((externalId: string | number) => {
        setFavorites(prev => {
            const next = new Set(prev);
            next.add(String(externalId));
            writeCookie(next);
            return next;
        });
    }, []);

    const removeFavorite = useCallback((externalId: string | number) => {
        setFavorites(prev => {
            const next = new Set(prev);
            next.delete(String(externalId));
            writeCookie(next);
            return next;
        });
    }, []);

    const clearFavorites = useCallback(() => {
        const empty = new Set<string>();
        writeCookie(empty);
        setFavorites(empty);
    }, []);

    return {
        favorites,
        favoriteCount: favorites.size,
        isFavorite,
        toggleFavorite,
        addFavorite,
        removeFavorite,
        clearFavorites,
    };
}
