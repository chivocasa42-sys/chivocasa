'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useFavorites } from '@/hooks/useFavorites';

const NAV_LINKS = [
    { href: '/', label: 'Inicio', icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0a1 1 0 01-1-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 01-1 1' },
    { href: '/valuador-de-inmuebles', label: 'Valuador', icon: 'M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z' },
    { href: '/tendencias', label: 'Tendencias', icon: 'M13 7h8m0 0v8m0-8l-8 8-4-4-6 6' },
    { href: '/favoritos', label: 'Favoritos', icon: 'M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z' },
];

interface NavbarProps {
    totalListings: number;
    lastUpdated?: string;
    onRefresh: () => void;
}

export default function Navbar({ totalListings, onRefresh }: NavbarProps) {
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [mobileOpen, setMobileOpen] = useState(false);
    const pathname = usePathname();
    const router = useRouter();
    const { favoriteCount } = useFavorites();

    const handleRefresh = async () => {
        setIsRefreshing(true);
        await onRefresh();
        setTimeout(() => setIsRefreshing(false), 1000);
    };

    const isActive = (href: string) => {
        if (href.startsWith('/#')) return false;
        if (href === '/') return pathname === '/';
        return pathname.startsWith(href);
    };

    const handleNavClick = (e: React.MouseEvent, href: string) => {
        if (href.startsWith('/#')) {
            const hash = href.slice(1); // e.g. "#departamentos"
            if (pathname === '/') {
                // Already on home — just smooth-scroll to the section
                e.preventDefault();
                document.querySelector(hash)?.scrollIntoView({ behavior: 'smooth' });
            } else {
                // On another page — use Next.js router to navigate to home, then scroll
                e.preventDefault();
                router.push('/' + hash);
            }
        }
    };

    return (
        <nav className="bg-white border-b border-slate-200 sticky top-0 z-40">
            <div className="container mx-auto px-4 max-w-7xl">
                <div className="flex items-center justify-between h-14">
                    {/* Brand */}
                    <Link href="/" className="no-underline flex items-center gap-2">
                        <img src="/sivarcasaslogo.webp" alt="SivarCasas" className="h-8 w-8 object-contain" />
                        <span className="text-lg font-extrabold tracking-tight leading-none">
                            <span className="text-[var(--primary)]">SIVAR</span>
                            <span className="text-slate-800">CASAS</span>
                        </span>
                    </Link>

                    {/* Desktop nav links */}
                    <div className="hidden md:flex items-center gap-1">
                        {NAV_LINKS.map(link => (
                            <Link
                                key={link.href}
                                href={link.href}
                                onClick={e => handleNavClick(e, link.href)}
                                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium transition-colors no-underline ${isActive(link.href)
                                    ? 'bg-[var(--primary)] text-white'
                                    : 'text-[var(--text-secondary)] hover:bg-[var(--bg-subtle)]'
                                    }`}
                            >
                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={link.icon} />
                                </svg>
                                {link.label}
                                {link.href === '/favoritos' && favoriteCount > 0 && (
                                    <span className={`ml-0.5 min-w-[18px] h-[18px] flex items-center justify-center rounded-full text-[10px] font-bold leading-none ${
                                        isActive(link.href)
                                            ? 'bg-white text-[var(--primary)]'
                                            : 'bg-red-500 text-white'
                                    }`}>
                                        {favoriteCount}
                                    </span>
                                )}
                            </Link>
                        ))}
                    </div>

                    {/* Right side: active count + refresh + mobile hamburger */}
                    <div className="flex items-center gap-2">
                        <span className="inline-flex items-center gap-1.5 text-xs sm:text-sm text-[var(--text-secondary)]">
                            <span className="w-2 h-2 bg-[var(--success)] rounded-full animate-pulse"></span>
                            <span className="font-semibold">{totalListings.toLocaleString()}</span>
                            <span className="hidden sm:inline">activos</span>
                        </span>
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

                        {/* Mobile hamburger */}
                        <button
                            onClick={() => setMobileOpen(prev => !prev)}
                            className="md:hidden p-2 rounded-full hover:bg-[var(--bg-subtle)] transition-colors"
                            aria-label="Menú"
                        >
                            <svg className="w-5 h-5 text-[var(--text-secondary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                                {mobileOpen ? (
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                ) : (
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                                )}
                            </svg>
                        </button>
                    </div>
                </div>

                {/* Mobile dropdown */}
                {mobileOpen && (
                    <div className="md:hidden pb-3 border-t border-[var(--border-light)] mt-1 pt-2 flex flex-col gap-1">
                        {NAV_LINKS.map(link => (
                            <Link
                                key={link.href}
                                href={link.href}
                                onClick={e => { handleNavClick(e, link.href); setMobileOpen(false); }}
                                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors no-underline ${isActive(link.href)
                                    ? 'bg-[var(--primary)] text-white'
                                    : 'text-[var(--text-secondary)] hover:bg-[var(--bg-subtle)]'
                                    }`}
                            >
                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={link.icon} />
                                </svg>
                                {link.label}
                                {link.href === '/favoritos' && favoriteCount > 0 && (
                                    <span className={`ml-auto min-w-[18px] h-[18px] flex items-center justify-center rounded-full text-[10px] font-bold leading-none ${
                                        isActive(link.href)
                                            ? 'bg-white text-[var(--primary)]'
                                            : 'bg-red-500 text-white'
                                    }`}>
                                        {favoriteCount}
                                    </span>
                                )}
                            </Link>
                        ))}
                    </div>
                )}
            </div>
        </nav>
    );
}
