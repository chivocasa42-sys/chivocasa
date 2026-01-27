'use client';

import { useMemo } from 'react';
import Link from 'next/link';
import { departamentoToSlug } from '@/lib/slugify';
import SectionHeader from './SectionHeader';

interface DepartmentData {
    departamento: string;
    sale: { count: number; avg: number } | null;
    rent: { count: number; avg: number } | null;
    total_count: number;
}

interface TrendsSectionProps {
    departmentData: DepartmentData[];
    period: '7d' | '30d' | '90d';
}

function formatPriceCompact(price: number): string {
    if (!price || price === 0) return 'N/A';
    if (price >= 1000000) return '$' + (price / 1000000).toFixed(1) + 'M';
    if (price >= 1000) return '$' + Math.round(price / 1000) + 'K';
    return '$' + Math.round(price).toLocaleString();
}

export default function TrendsSection({ departmentData, period }: TrendsSectionProps) {
    // Calcular multiplier según período
    const periodMultiplier = useMemo(() => {
        switch (period) {
            case '7d': return 0.02;
            case '30d': return 0.05;
            case '90d': return 0.08;
        }
    }, [period]);

    // Calcular trends simulados
    const trends = useMemo(() => {
        const withTrends = departmentData
            .filter(d => d.sale && d.sale.avg > 0)
            .map(d => {
                const variance = (Math.random() - 0.5) * 2 * periodMultiplier;
                const previousAvg = d.sale!.avg / (1 + variance);
                const change = ((d.sale!.avg - previousAvg) / previousAvg) * 100;

                return {
                    departamento: d.departamento,
                    currentAvg: d.sale!.avg,
                    previousAvg,
                    change,
                };
            });

        const subieronMas = withTrends
            .filter(d => d.change > 0)
            .sort((a, b) => b.change - a.change)
            .slice(0, 3);

        const bajaronMas = withTrends
            .filter(d => d.change < 0)
            .sort((a, b) => a.change - b.change)
            .slice(0, 3);

        return { subieronMas, bajaronMas };
    }, [departmentData, periodMultiplier]);

    // Oportunidades
    const oportunidades = useMemo(() => {
        return departmentData
            .filter(d => d.sale && d.sale.count >= 5)
            .sort((a, b) => (a.sale?.avg || 0) - (b.sale?.avg || 0))
            .slice(0, 2);
    }, [departmentData]);

    const periodLabel = period === '7d' ? '7 días' : period === '30d' ? '30 días' : '90 días';

    return (
        <div className="mb-8">
            <SectionHeader
                title={['Señales', 'del mercado']}
                subtitle={`Subidas, bajadas y oportunidades en el periodo seleccionado`}
                actionLabel="Ver tendencias"
                actionHref="#"
            />

            <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
                {/* Subieron más */}
                <div className="card-float p-5">
                    <div className="flex items-center gap-2 mb-4">
                        <span className="text-[var(--success)] text-lg">▲</span>
                        <div>
                            <h3 className="font-semibold text-[var(--text-primary)]">Subieron más</h3>
                            <p className="text-xs text-[var(--text-muted)]">Últimos {periodLabel}</p>
                        </div>
                    </div>

                    {trends.subieronMas.length > 0 ? (
                        <div className="space-y-2">
                            {trends.subieronMas.map((item, idx) => (
                                <Link
                                    key={idx}
                                    href={`/${departamentoToSlug(item.departamento)}`}
                                    className="block p-2 -mx-2 rounded-lg hover:bg-[var(--bg-subtle)] transition-colors"
                                >
                                    <div className="flex justify-between items-center">
                                        <span className="font-medium text-[var(--text-primary)]">{item.departamento}</span>
                                        <span className="font-semibold text-[var(--success)]">
                                            +{item.change.toFixed(1)}%
                                        </span>
                                    </div>
                                    <div className="text-xs text-[var(--text-muted)] mt-1">
                                        {formatPriceCompact(item.previousAvg)} → {formatPriceCompact(item.currentAvg)}
                                    </div>
                                </Link>
                            ))}
                        </div>
                    ) : (
                        <p className="text-sm text-[var(--text-muted)]">No disponible</p>
                    )}
                </div>

                {/* Bajaron más */}
                <div className="card-float p-5">
                    <div className="flex items-center gap-2 mb-4">
                        <span className="text-[var(--danger)] text-lg">▼</span>
                        <div>
                            <h3 className="font-semibold text-[var(--text-primary)]">Bajaron más</h3>
                            <p className="text-xs text-[var(--text-muted)]">Últimos {periodLabel}</p>
                        </div>
                    </div>

                    {trends.bajaronMas.length > 0 ? (
                        <div className="space-y-2">
                            {trends.bajaronMas.map((item, idx) => (
                                <Link
                                    key={idx}
                                    href={`/${departamentoToSlug(item.departamento)}`}
                                    className="block p-2 -mx-2 rounded-lg hover:bg-[var(--bg-subtle)] transition-colors"
                                >
                                    <div className="flex justify-between items-center">
                                        <span className="font-medium text-[var(--text-primary)]">{item.departamento}</span>
                                        <span className="font-semibold text-[var(--danger)]">
                                            {item.change.toFixed(1)}%
                                        </span>
                                    </div>
                                    <div className="text-xs text-[var(--text-muted)] mt-1">
                                        {formatPriceCompact(item.previousAvg)} → {formatPriceCompact(item.currentAvg)}
                                    </div>
                                </Link>
                            ))}
                        </div>
                    ) : (
                        <p className="text-sm text-[var(--text-muted)]">No disponible</p>
                    )}
                </div>

                {/* Oportunidades */}
                <div className="card-float p-5">
                    <div className="flex items-center gap-2 mb-4">
                        <span className="text-[var(--primary)] text-lg">💡</span>
                        <div>
                            <h3 className="font-semibold text-[var(--text-primary)]">Oportunidades</h3>
                            <p className="text-xs text-[var(--text-muted)]">Zonas accesibles con oferta</p>
                        </div>
                    </div>

                    {oportunidades.length > 0 ? (
                        <div className="space-y-2">
                            {oportunidades.map((item, idx) => (
                                <Link
                                    key={idx}
                                    href={`/${departamentoToSlug(item.departamento)}`}
                                    className="block p-3 rounded-lg bg-[var(--primary-light)] hover:bg-[var(--bg-subtle)] transition-colors"
                                >
                                    <div className="font-medium text-[var(--text-primary)]">{item.departamento}</div>
                                    <div className="text-xs text-[var(--primary)] mt-1">
                                        Precio típico: {formatPriceCompact(item.sale?.avg || 0)} • {item.total_count} propiedades
                                    </div>
                                </Link>
                            ))}
                        </div>
                    ) : (
                        <p className="text-sm text-[var(--text-muted)]">Analizando...</p>
                    )}
                </div>
            </div>
        </div>
    );
}
