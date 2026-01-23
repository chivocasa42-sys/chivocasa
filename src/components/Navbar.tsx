'use client';

import { useState } from 'react';

interface NavbarProps {
    totalListings: number;
    onRefresh: () => void;
}

export default function Navbar({ totalListings, onRefresh }: NavbarProps) {
    const [isRefreshing, setIsRefreshing] = useState(false);

    const handleRefresh = async () => {
        setIsRefreshing(true);
        await onRefresh();
        setIsRefreshing(false);
    };

    return (
        <nav className="navbar py-4 mb-6">
            <div className="container mx-auto px-4 flex justify-between items-center">
                <a href="/" className="flex items-center gap-2 text-xl font-bold no-underline text-inherit">
                    <svg className="w-6 h-6 text-[var(--accent)]" fill="currentColor" viewBox="0 0 16 16">
                        <path d="M8.707 1.5a1 1 0 0 0-1.414 0L.646 8.146a.5.5 0 0 0 .708.708L2 8.207V13.5A1.5 1.5 0 0 0 3.5 15h9a1.5 1.5 0 0 0 1.5-1.5V8.207l.646.647a.5.5 0 0 0 .708-.708L13 5.793V2.5a.5.5 0 0 0-.5-.5h-1a.5.5 0 0 0-.5.5v1.293L8.707 1.5Z" />
                    </svg>
                    <span>ChivoCasas</span>
                </a>
                <div className="flex items-center gap-3">
                    <span className="bg-gray-500 text-white text-sm px-3 py-1 rounded-lg">
                        {totalListings} listings
                    </span>
                    <button
                        onClick={handleRefresh}
                        disabled={isRefreshing}
                        className="flex items-center gap-2 px-3 py-1 border border-gray-300 rounded-lg bg-white hover:bg-gray-50 transition disabled:opacity-50"
                    >
                        <svg
                            className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`}
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                        >
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                        </svg>
                        Refresh
                    </button>
                </div>
            </div>
        </nav>
    );
}
