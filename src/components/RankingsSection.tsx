'use client';

import RankingCard from './RankingCard';

interface RankingItem {
    name: string;
    value: number;
}

interface RankingsSectionProps {
    topExpensive: RankingItem[];
    topCheap: RankingItem[];
    topActive: RankingItem[];
}

function formatPriceCompact(price: number): string {
    if (!price || price === 0) return 'N/A';
    if (price >= 1000000) return '$' + (price / 1000000).toFixed(1) + 'M';
    if (price >= 1000) return '$' + Math.round(price / 1000) + 'K';
    return '$' + Math.round(price).toLocaleString();
}

export default function RankingsSection({ topExpensive, topCheap, topActive }: RankingsSectionProps) {
    return (
        <div className="mb-8">
            <h2 className="text-lg font-semibold text-[var(--text-primary)] mb-4">
                Rankings del Mercado
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
                <RankingCard
                    title="ZONAS MÁS CARAS"
                    subtitle="Por precio típico (mediana)"
                    items={topExpensive.slice(0, 3).map(item => ({
                        name: item.name,
                        value: formatPriceCompact(item.value)
                    }))}
                    valueType="expensive"
                />

                <RankingCard
                    title="ZONAS MÁS ECONÓMICAS"
                    subtitle="Por precio típico (mediana)"
                    items={topCheap.slice(0, 3).map(item => ({
                        name: item.name,
                        value: formatPriceCompact(item.value)
                    }))}
                    valueType="cheap"
                />

                <RankingCard
                    title="ZONAS MÁS ACTIVAS"
                    subtitle="Activos hoy"
                    items={topActive.slice(0, 3).map(item => ({
                        name: item.name,
                        value: item.value
                    }))}
                    valueType="active"
                />
            </div>
        </div>
    );
}
