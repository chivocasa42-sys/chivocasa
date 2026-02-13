'use client';

import { useState, useCallback, useEffect, useRef, createContext, useContext, ReactNode } from 'react';

const COOKIE_NAME = 'sivarcasas_favorites';
const COOKIE_MAX_AGE = 60 * 60 * 24 * 365; // 1 year
const MAX_FAVORITES = 25;

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

interface FavoritesContextValue {
    favorites: Set<string>;
    favoriteCount: number;
    isFavorite: (externalId: string | number) => boolean;
    toggleFavorite: (externalId: string | number) => boolean;
    addFavorite: (externalId: string | number) => boolean;
    removeFavorite: (externalId: string | number) => void;
    clearFavorites: () => void;
    isAtLimit: boolean;
    limitMessage: string | null;
}

const FavoritesContext = createContext<FavoritesContextValue | null>(null);

/**
 * Provider that holds the single shared favorites state.
 * Wrap your app (e.g. in layout.tsx) with <FavoritesProvider>.
 */
export function FavoritesProvider({ children }: { children: ReactNode }) {
    const [favorites, setFavorites] = useState<Set<string>>(new Set());
    const [limitMessage, setLimitMessage] = useState<string | null>(null);
    const limitTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

    const showLimitWarning = useCallback(() => {
        setLimitMessage('Has alcanzado el máximo de 25 favoritos. Elimina alguno para agregar más.');
        if (limitTimer.current) clearTimeout(limitTimer.current);
        limitTimer.current = setTimeout(() => setLimitMessage(null), 4000);
    }, []);

    // Hydrate from cookie on mount
    useEffect(() => {
        setFavorites(readCookie());
    }, []);

    const isFavorite = useCallback(
        (externalId: string | number) => favorites.has(String(externalId)),
        [favorites]
    );

    const toggleFavorite = useCallback((externalId: string | number): boolean => {
        let added = false;
        setFavorites(prev => {
            const next = new Set(prev);
            const key = String(externalId);
            if (next.has(key)) {
                next.delete(key);
            } else {
                if (next.size >= MAX_FAVORITES) {
                    showLimitWarning();
                    return prev;
                }
                next.add(key);
                added = true;
            }
            writeCookie(next);
            return next;
        });
        return added;
    }, [showLimitWarning]);

    const addFavorite = useCallback((externalId: string | number): boolean => {
        let added = false;
        setFavorites(prev => {
            if (prev.size >= MAX_FAVORITES) {
                showLimitWarning();
                return prev;
            }
            const next = new Set(prev);
            next.add(String(externalId));
            writeCookie(next);
            added = true;
            return next;
        });
        return added;
    }, [showLimitWarning]);

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

    const value: FavoritesContextValue = {
        favorites,
        favoriteCount: favorites.size,
        isFavorite,
        toggleFavorite,
        addFavorite,
        removeFavorite,
        clearFavorites,
        isAtLimit: favorites.size >= MAX_FAVORITES,
        limitMessage,
    };

    return (
        <FavoritesContext.Provider value={value}>
            {children}
            {/* Global limit toast */}
            {limitMessage && (
                <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-[200] animate-fade-in">
                    <div className="bg-red-600 text-white px-5 py-3 rounded-xl shadow-lg text-sm font-medium flex items-center gap-2 max-w-md">
                        <svg className="w-5 h-5 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        {limitMessage}
                    </div>
                </div>
            )}
        </FavoritesContext.Provider>
    );
}

/**
 * Hook to access the shared favorites state.
 * Must be used inside a <FavoritesProvider>.
 */
export function useFavorites(): FavoritesContextValue {
    const ctx = useContext(FavoritesContext);
    if (!ctx) {
        throw new Error('useFavorites must be used within a <FavoritesProvider>');
    }
    return ctx;
}
