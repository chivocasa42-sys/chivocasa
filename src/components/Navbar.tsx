'use client';

import { useState } from 'react';

interface NavbarProps {
    totalListings: number;
    lastUpdated?: string;
    onRefresh: () => void;
}

function formatRelativeTime(isoString?: string): string {
    if (!isoString) return '';
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / (1000 * 60));

    if (diffMins < 1) return 'Ahora';
    if (diffMins < 60) return `Hace ${diffMins} min`;

    return date.toLocaleTimeString('es-SV', {
        hour: 'numeric',
        minute: '2-digit',
        hour12: true
    });
}

export default function Navbar({ totalListings, lastUpdated, onRefresh }: NavbarProps) {
    const [isRefreshing, setIsRefreshing] = useState(false);

    const handleRefresh = async () => {
        setIsRefreshing(true);
        await onRefresh();
        setTimeout(() => setIsRefreshing(false), 1000);
    };

    return (
        <nav className="navbar-glass sticky top-0 z-40 py-4 mb-6">
            <div className="container mx-auto px-4">
                <div className="flex justify-between items-center">
                    {/* Logo */}
                    <a href="/" className="flex items-center gap-2 text-xl font-bold no-underline text-[var(--text-primary)]">
                        <span className="text-2xl">🏠</span>
                        <span>ChivoCasas</span>
                    </a>

                    {/* Stats & Actions */}
                    <div className="flex items-center gap-4">
                        {/* Badge */}
                        <span className="badge-count">
                            {totalListings.toLocaleString()} activos
                        </span>

                        {/* Timestamp */}
                        {lastUpdated && (
                            <span className="text-sm text-[var(--text-muted)] hidden sm:inline">
                                {formatRelativeTime(lastUpdated)}
                            </span>
                        )}

                        {/* Refresh */}
                        <button
                            onClick={handleRefresh}
                            disabled={isRefreshing}
                            className="p-2 rounded-lg hover:bg-[var(--bg-subtle)] transition-colors disabled:opacity-50"
                            title="Actualizar datos"
                        >
                            <svg
                                className={`w-5 h-5 text-[var(--text-secondary)] ${isRefreshing ? 'animate-spin' : ''}`}
                                fill="none"
                                stroke="currentColor"
                                viewBox="0 0 24 24"
                            >
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                            </svg>
                        </button>
                    </div>
                </div>
            </div>
        </nav>
    );
}
