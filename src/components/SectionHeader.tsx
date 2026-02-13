'use client';

import Link from 'next/link';

interface SectionHeaderProps {
    title: string[];  // ['Primera parte', 'Parte con acento']
    subtitle?: string;
    actionLabel?: string;
    actionHref?: string;
}

export default function SectionHeader({
    title,
    subtitle,
    actionLabel,
    actionHref
}: SectionHeaderProps) {
    return (
        <div className="text-center mb-8">
            <h2 className="text-2xl md:text-3xl font-black text-[var(--text-primary)] tracking-tight mb-2">
                {title[0]} <span className="text-[var(--primary)]">{title[1]}</span>
            </h2>
            {subtitle && (
                <p className="text-base text-[var(--text-muted)] mx-auto leading-relaxed max-w-3xl mb-3">
                    {subtitle}
                </p>
            )}
            {actionLabel && actionHref && (
                <Link
                    href={actionHref}
                    className="inline-flex items-center gap-1 mt-3 text-sm font-semibold text-[var(--primary)] hover:opacity-80 transition-opacity"
                >
                    {actionLabel}
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                        <path d="M6 4L10 8L6 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                </Link>
            )}
        </div>
    );
}
