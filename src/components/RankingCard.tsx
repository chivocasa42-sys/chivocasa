'use client';

import Link from 'next/link';
import { departamentoToSlug } from '@/lib/slugify';

interface RankingItem {
    name: string;
    value: string | number;
    slug?: string;
}

interface RankingCardProps {
    title: string;
    subtitle: string;
    items: RankingItem[];
    valueType?: 'expensive' | 'cheap' | 'active';
}

export default function RankingCard({ title, subtitle, items, valueType = 'active' }: RankingCardProps) {
    const getValueClass = () => {
        switch (valueType) {
            case 'expensive': return 'ranking-value-expensive';
            case 'cheap': return 'ranking-value-cheap';
            case 'active': return 'ranking-value-active';
        }
    };

    return (
        <div className="card-float card-ranking p-5">
            {/* Header */}
            <div className="mb-4">
                <h3 className="font-semibold text-[var(--text-primary)] text-base">
                    {title}
                </h3>
                <p className="text-xs text-[var(--text-muted)] mt-0.5">
                    {subtitle}
                </p>
            </div>

            {/* Items */}
            <div className="space-y-1">
                {items.map((item, idx) => {
                    const slug = item.slug || departamentoToSlug(item.name);

                    return (
                        <Link
                            key={idx}
                            href={`/${slug}`}
                            className="ranking-item"
                        >
                            <span className="ranking-number">{idx + 1}.</span>
                            <span className="ranking-name">{item.name}</span>
                            <span className={`ranking-value ${getValueClass()}`}>
                                {typeof item.value === 'number' ? item.value.toLocaleString() : item.value}
                            </span>
                        </Link>
                    );
                })}
            </div>
        </div>
    );
}
