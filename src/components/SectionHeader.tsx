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
        <div className="section-header-simple">
            <div className="section-header-left">
                <h2 className="section-title-simple">
                    {title[0]} <span className="section-title-accent">{title[1]}</span>
                </h2>
                {subtitle && (
                    <p className="section-subtitle-simple">{subtitle}</p>
                )}
            </div>
            {actionLabel && actionHref && (
                <Link href={actionHref} className="section-action-simple">
                    {actionLabel}
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                        <path d="M6 4L10 8L6 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                </Link>
            )}
        </div>
    );
}
