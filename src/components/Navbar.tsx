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
                        className="flex items-center gap-2.5 no-underline group"
                    >
                        <div className="flex items-center justify-center w-9 h-9 bg-blue-50 rounded-xl group-hover:scale-105 transition-transform">
                            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-6 h-6">
                                <path d="M3 10L12 3L21 10V20C21 20.5523 20.5523 21 20 21H4C3.44772 21 3 20.5523 3 20V10Z" stroke="#2563eb" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                                <rect x="7" y="14" width="2" height="3" rx="0.5" fill="#2563eb" />
                                <rect x="11" y="11" width="2" height="6" rx="0.5" fill="#2563eb" />
                                <rect x="15" y="13" width="2" height="4" rx="0.5" fill="#3b82f6" />
                                <path d="M7 14L11 11L15 13" stroke="#2563eb" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                            </svg>
                        </div>
                        <span className="text-xl font-extrabold tracking-tight text-slate-900">
                            Chivo<span className="text-blue-600">Casa</span>
                        </span>
                    </Link>

                    {/* Nav Links - Desktop */}
                    <div className="hidden md:flex items-center gap-6">
                        <Link
                            href="#departamentos"
                            className="text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors no-underline"
                        >
                            Departamentos
                        </Link>
                        <Link
                            href="#tendencias"
                            className="text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors no-underline"
                        >
                            Tendencias
                        </Link>
                        <Link
                            href="#rankings"
                            className="text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors no-underline"
                        >
                            Rankings
                        </Link>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-3">
                        {/* Badge */}
                        <span className="hidden sm:inline-flex items-center gap-1.5 text-sm text-[var(--text-secondary)]">
                            <span className="w-2 h-2 bg-[var(--success)] rounded-full animate-pulse"></span>
                            {totalListings.toLocaleString()} activos
                        </span>

                        {/* Refresh */}
                        <button
                            onClick={handleRefresh}
                            disabled={isRefreshing}
                            className="p-2 rounded-full hover:bg-[var(--bg-subtle)] transition-colors disabled:opacity-50"
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

                        {/* CTA Button */}
                        <a
                            href="#departamentos"
                            className="btn-primary"
                            style={{
                                borderRadius: '999px',
                                fontSize: '0.875rem',
                                padding: '0.5rem 1rem'
                            }}
                        >
                            Explorar
                        </a>
                    </div>
                </div>
            </div>
        </nav>
    );
}

