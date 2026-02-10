'use client';

import { useState } from 'react';
import Link from 'next/link';

interface NavbarProps {
    totalListings: number;
    lastUpdated?: string;
    onRefresh: () => void;
}

export default function Navbar({ totalListings, onRefresh }: NavbarProps) {
    const [isRefreshing, setIsRefreshing] = useState(false);

    const handleRefresh = async () => {
        setIsRefreshing(true);
        await onRefresh();
        setTimeout(() => setIsRefreshing(false), 1000);
    };

    return (
        <nav className="navbar-glass sticky top-0 z-40 py-4">
            <div className="container mx-auto px-4 max-w-7xl">
                <div className="flex justify-between items-center">
                    {/* Logo */}
                    <Link
                        href="/"
                        className="flex items-center gap-2 no-underline group"
                    >
                        <img
                            src="/logo.webp"
                            alt="SivarCasas"
                            width={120}
                            height={40}
                            className="h-10 w-auto group-hover:scale-105 transition-transform"
                        />
                    </Link>

                    {/* Spacer for layout balance */}
                    <div className="hidden md:flex items-center gap-6">
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-2 sm:gap-3">
                        {/* Badge - Visible on all devices */}
                        <span className="inline-flex items-center gap-1 sm:gap-1.5 text-xs sm:text-sm text-[var(--text-secondary)]">
                            <span className="w-1.5 sm:w-2 h-1.5 sm:h-2 bg-[var(--success)] rounded-full animate-pulse"></span>
                            <span className="font-medium">{totalListings.toLocaleString()}</span>
                            <span className="hidden sm:inline">activos</span>
                        </span>

                        {/* Refresh */}
                        <button
                            onClick={handleRefresh}
                            disabled={isRefreshing}
                            className="p-2 rounded-full hover:bg-[var(--bg-subtle)] transition-colors disabled:opacity-50"
                            title="Actualizar datos"
                            aria-label="Actualizar datos"
                        >
                            <svg
                                className={`w-5 h-5 text-[var(--text-secondary)] ${isRefreshing ? 'animate-spin' : ''}`}
                                fill="none"
                                stroke="currentColor"
                                viewBox="0 0 24 24"
                                aria-hidden="true"
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

