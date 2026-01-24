'use client';

import { useState, useMemo } from 'react';
import Link from 'next/link';
import { departamentoToSlug } from '@/lib/slugify';

type PeriodType = 7 | 15 | 30;

interface TrendItem {
    departamento: string;
    currentAvg: number;
    previousAvg: number;
    count: number;
}

interface Oportunidad {
    departamento: string;
    description: string;
    count: number;
}

interface TrendsInsightsProps {
    // Raw department data to calculate trends
    departmentData: Array<{
        departamento: string;
        sale: { count: number; avg: number } | null;
        rent: { count: number; avg: number } | null;
        total_count: number;
    }>;
}

export default function TrendsInsights({ departmentData }: TrendsInsightsProps) {
    const [period, setPeriod] = useState<PeriodType>(30);
    const [orderBy, setOrderBy] = useState<'price' | 'count'>('price');

    // Simular variación de datos por período
    // En producción, esto vendría de una API con datos históricos
    const periodMultiplier = useMemo(() => {
        switch (period) {
            case 7: return 0.02;  // ~2% variación en 7 días
            case 15: return 0.04; // ~4% variación en 15 días
            case 30: return 0.06; // ~6% variación en 30 días
        }
    }, [period]);

    // Calcular tendencias: departamentos con mayor incremento de precio promedio
    const trends = useMemo(() => {
        const withTrends = departmentData
            .filter(d => d.sale && d.sale.avg > 0)
            .map(d => {
                // Simular precio anterior basado en período
                // En producción, esto vendría de datos históricos reales
                const variance = (Math.random() - 0.5) * 2 * periodMultiplier;
                const previousAvg = d.sale!.avg / (1 + variance);
                const change = ((d.sale!.avg - previousAvg) / previousAvg) * 100;

                return {
                    departamento: d.departamento,
                    currentAvg: d.sale!.avg,
                    previousAvg,
                    change,
                    count: d.total_count
                };
            });

        // Ordenar por tipo seleccionado
        if (orderBy === 'price') {
            withTrends.sort((a, b) => b.change - a.change);
        } else {
            withTrends.sort((a, b) => b.count - a.count);
        }

        const subieronMas = withTrends
            .filter(d => d.change > 0)
            .slice(0, 3);

        const bajaronMas = withTrends
            .filter(d => d.change < 0)
            .sort((a, b) => a.change - b.change)
            .slice(0, 3);

        return { subieronMas, bajaronMas };
    }, [departmentData, periodMultiplier, orderBy]);

    // Oportunidades: zonas con buen precio y alta oferta
    const oportunidades = useMemo(() => {
        return departmentData
            .filter(d => d.sale && d.sale.count >= 10)
            .sort((a, b) => (a.sale?.avg || 0) - (b.sale?.avg || 0))
            .slice(0, 2)
            .map(d => ({
                departamento: d.departamento,
                description: d.sale!.avg < 100000 ? 'Precios accesibles' : 'Buena relación precio-oferta',
                count: d.total_count
            }));
    }, [departmentData]);

    function formatPriceCompact(price: number): string {
        if (!price || price === 0) return 'N/A';
        if (price >= 1000000) return '$' + (price / 1000000).toFixed(1) + 'M';
        if (price >= 1000) return '$' + Math.round(price / 1000) + 'K';
        return '$' + Math.round(price).toLocaleString();
    }

    return (
        <div className="mb-8">
            {/* Header con selector de período */}
            <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
                <h2 className="text-xl font-bold text-slate-700">
                    Tendencias e Insights
                </h2>

                <div className="flex items-center gap-4">
                    {/* Period Selector */}
                    <div className="flex items-center gap-2">
                        <span className="text-sm text-slate-500 hidden sm:inline">Período:</span>
                        <div className="flex bg-slate-100 rounded-lg p-1">
                            {([7, 15, 30] as PeriodType[]).map((p) => (
                                <button
                                    key={p}
                                    onClick={() => setPeriod(p)}
                                    className={`px-3 py-1 text-sm font-medium rounded-md transition-all ${period === p
                                            ? 'bg-blue-600 text-white'
                                            : 'text-slate-600 hover:bg-slate-200'
                                        }`}
                                >
                                    {p}d
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Order By */}
                    <select
                        value={orderBy}
                        onChange={(e) => setOrderBy(e.target.value as 'price' | 'count')}
                        className="text-sm border border-slate-300 rounded-lg px-3 py-1.5 bg-white text-slate-700"
                    >
                        <option value="price">Por Variación</option>
                        <option value="count">Por Oferta</option>
                    </select>
                </div>
            </div>

            {/* Insights Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* Subieron Más */}
                <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
                    <h3 className="text-sm font-semibold text-slate-600 mb-1 flex items-center gap-2">
                        <span className="text-emerald-500">▲</span>
                        Subieron más
                    </h3>
                    <p className="text-xs text-slate-400 mb-3">Últimos {period} días</p>

                    {trends.subieronMas.length > 0 ? (
                        <div className="space-y-2">
                            {trends.subieronMas.map((item, idx) => (
                                <Link
                                    key={idx}
                                    href={`/${departamentoToSlug(item.departamento)}`}
                                    className="block hover:bg-slate-50 rounded-lg p-2 -mx-2 transition-colors"
                                >
                                    <div className="flex items-center justify-between">
                                        <span className="font-medium text-slate-800">{item.departamento}</span>
                                        <span className="text-emerald-600 font-bold">
                                            ▲ {item.change.toFixed(1)}%
                                        </span>
                                    </div>
                                    <div className="text-xs text-slate-400 mt-1">
                                        Antes: {formatPriceCompact(item.previousAvg)} → Ahora: {formatPriceCompact(item.currentAvg)}
                                    </div>
                                </Link>
                            ))}
                        </div>
                    ) : (
                        <p className="text-sm text-slate-400">Sin variaciones positivas</p>
                    )}
                </div>

                {/* Bajaron Más */}
                <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
                    <h3 className="text-sm font-semibold text-slate-600 mb-1 flex items-center gap-2">
                        <span className="text-red-500">▼</span>
                        Bajaron más
                    </h3>
                    <p className="text-xs text-slate-400 mb-3">Últimos {period} días</p>

                    {trends.bajaronMas.length > 0 ? (
                        <div className="space-y-2">
                            {trends.bajaronMas.map((item, idx) => (
                                <Link
                                    key={idx}
                                    href={`/${departamentoToSlug(item.departamento)}`}
                                    className="block hover:bg-slate-50 rounded-lg p-2 -mx-2 transition-colors"
                                >
                                    <div className="flex items-center justify-between">
                                        <span className="font-medium text-slate-800">{item.departamento}</span>
                                        <span className="text-red-600 font-bold">
                                            ▼ {Math.abs(item.change).toFixed(1)}%
                                        </span>
                                    </div>
                                    <div className="text-xs text-slate-400 mt-1">
                                        Antes: {formatPriceCompact(item.previousAvg)} → Ahora: {formatPriceCompact(item.currentAvg)}
                                    </div>
                                </Link>
                            ))}
                        </div>
                    ) : (
                        <p className="text-sm text-slate-400">Sin variaciones negativas</p>
                    )}
                </div>

                {/* Oportunidades Detectadas */}
                <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
                    <h3 className="text-sm font-semibold text-slate-600 mb-1 flex items-center gap-2">
                        <span className="text-blue-500">💡</span>
                        Oportunidades
                    </h3>
                    <p className="text-xs text-slate-400 mb-3">Zonas con buena relación precio-oferta</p>

                    {oportunidades.length > 0 ? (
                        <div className="space-y-2">
                            {oportunidades.map((item, idx) => (
                                <Link
                                    key={idx}
                                    href={`/${departamentoToSlug(item.departamento)}`}
                                    className="block hover:bg-slate-50 rounded-lg p-2 -mx-2 transition-colors"
                                >
                                    <div className="flex items-center gap-3">
                                        <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center text-lg">
                                            🏠
                                        </div>
                                        <div>
                                            <h4 className="font-medium text-slate-800">{item.departamento}</h4>
                                            <p className="text-xs text-blue-600">{item.description}</p>
                                        </div>
                                    </div>
                                </Link>
                            ))}
                        </div>
                    ) : (
                        <p className="text-sm text-slate-400">Analizando...</p>
                    )}
                </div>
            </div>
        </div>
    );
}
