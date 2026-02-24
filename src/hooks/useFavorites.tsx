'use client';

import { useState, useCallback, useEffect, useRef, createContext, useContext, ReactNode, startTransition } from 'react';

const COOKIE_NAME = 'sivarcasas_favorites';
const COOKIE_TIMESTAMP_NAME = 'sivarcasas_favorites_ts';
const COOKIE_MAX_AGE = 60 * 60 * 24 * 7; // 7 days in seconds
const COOKIE_MAX_AGE_MS = COOKIE_MAX_AGE * 1000; // 7 days in milliseconds
const MAX_FAVORITES = 25;

const EMPTY_SET = new Set<string>();

/** Read the favorites cookie and return the set of external_id strings. */
function readCookie(): Set<string> {
    if (typeof document === 'undefined') return EMPTY_SET;
    const match = document.cookie
        .split('; ')
        .find(row => row.startsWith(`${COOKIE_NAME}=`));
    if (!match) return EMPTY_SET;
    try {
        const decoded = decodeURIComponent(match.split('=')[1]);
        const ids: string[] = JSON.parse(decoded);
        if (!Array.isArray(ids) || ids.length === 0) return EMPTY_SET;
        return new Set(ids);
    } catch {
        return EMPTY_SET;
    }
}

/** Read the timestamp cookie that tracks when favorites were last saved. */
function readTimestampCookie(): number | null {
    if (typeof document === 'undefined') return null;
    const match = document.cookie
        .split('; ')
        .find(row => row.startsWith(`${COOKIE_TIMESTAMP_NAME}=`));
    if (!match) return null;
    try {
        const ts = parseInt(match.split('=')[1], 10);
        return isNaN(ts) ? null : ts;
    } catch {
        return null;
    }
}

/** Write the favorites set back to the cookie, along with a timestamp cookie. */
function writeCookie(ids: Set<string>): void {
    const value = encodeURIComponent(JSON.stringify([...ids]));
    const now = Date.now();
    document.cookie = `${COOKIE_NAME}=${value}; path=/; max-age=${COOKIE_MAX_AGE}; SameSite=Lax`;
    document.cookie = `${COOKIE_TIMESTAMP_NAME}=${now}; path=/; max-age=${COOKIE_MAX_AGE}; SameSite=Lax`;
}

/** Delete both favorites cookies immediately. */
function deleteCookies(): void {
    document.cookie = `${COOKIE_NAME}=; path=/; max-age=0; SameSite=Lax`;
    document.cookie = `${COOKIE_TIMESTAMP_NAME}=; path=/; max-age=0; SameSite=Lax`;
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
    const hydrated = useRef(false);

    const showLimitWarning = useCallback(() => {
        setLimitMessage('Has alcanzado el máximo de 25 favoritos. Elimina alguno para agregar más.');
        if (limitTimer.current) clearTimeout(limitTimer.current);
        limitTimer.current = setTimeout(() => setLimitMessage(null), 4000);
    }, []);

    // 1. Initial hydration from cookie (Client-side only)
    //    Also checks the timestamp — if favorites are older than 7 days, delete them.
    useEffect(() => {
        const initial = readCookie();
        const savedAt = readTimestampCookie();
        const now = Date.now();

        // If the timestamp exists and is older than 7 days, purge all favorites
        if (savedAt !== null && (now - savedAt) >= COOKIE_MAX_AGE_MS) {
            deleteCookies();
            hydrated.current = true;
            return; // favorites stay as empty Set
        }

        if (initial.size > 0) {
            startTransition(() => {
                setFavorites(initial);
            });
            // Refresh the cookie max-age so the 7-day timer resets from NOW
            // This ensures old favorites get a fresh 7-day window on each visit
            writeCookie(initial);
        }

        hydrated.current = true;
    }, []);

    // 2. Persist to cookie whenever favorites change (after hydration)
    useEffect(() => {
        // Skip writing the empty set on the initial render before hydration completes.
        // This prevents overwriting the real cookie with an empty set.
        if (!hydrated.current) return;

        writeCookie(favorites);
    }, [favorites]);

    const isFavorite = useCallback(
        (externalId: string | number) => favorites.has(String(externalId)),
        [favorites]
    );

    const toggleFavorite = useCallback((externalId: string | number): boolean => {
        let added = false;
        const key = String(externalId);

        setFavorites(prev => {
            const next = new Set(prev);
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
            if (prev.has(String(externalId))) return prev;

            const next = new Set(prev);
            next.add(String(externalId));
            added = true;
            return next;
        });
        return added;
    }, [showLimitWarning]);

    const removeFavorite = useCallback((externalId: string | number) => {
        setFavorites(prev => {
            const key = String(externalId);
            if (!prev.has(key)) return prev;
            const next = new Set(prev);
            next.delete(key);
            return next;
        });
    }, []);

    const clearFavorites = useCallback(() => {
        deleteCookies();
        setFavorites(EMPTY_SET);
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
