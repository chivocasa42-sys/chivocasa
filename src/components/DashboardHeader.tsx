'use client';

import Link from 'next/link';
import { departamentoToSlug } from '@/lib/slugify';

interface DashboardHeaderProps {
    stats: {
        avgSalePrice: number;
        avgRentPrice: number;
        totalActive: number;
        saleTrend: number;
        rentTrend: number;
    };
    topExpensive: Array<{ name: string; price: number }>;
    topCheap: Array<{ name: string; price: number }>;
    topActive: Array<{ name: string; count: number }>;
}

function formatPriceCompact(price: number): string {
    if (!price || price === 0) return 'N/A';
    if (price >= 1000000) {
        return '$' + (price / 1000000).toFixed(1) + 'M';
    }
    if (price >= 1000) {
        return '$' + Math.round(price / 1000) + 'K';
    }
    return '$' + Math.round(price).toLocaleString();
}

export default function DashboardHeader({ stats, topExpensive, topCheap, topActive }: DashboardHeaderProps) {
    return (
        <div className="mb-8">
            {/* KPI Strip - Gradient Blue Header */}
            <div className="bg-gradient-to-r from-blue-600 to-blue-800 rounded-xl p-6 mb-6 text-white">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    {/* Precio Medio Venta */}
                    <div className="bg-white/10 backdrop-blur rounded-lg p-4">
                        <div className="text-xs text-blue-200 uppercase tracking-wider mb-1">
                            Precio Promedio Venta
                        </div>
                        <div className="text-2xl md:text-3xl font-bold">
                            {formatPriceCompact(stats.avgSalePrice)}
                        </div>
                        {stats.saleTrend !== 0 && (
                            <div className={`text-sm mt-1 flex items-center gap-1 ${stats.saleTrend > 0 ? 'text-emerald-300' : 'text-red-300'}`}>
                                {stats.saleTrend > 0 ? '▲' : '▼'} {Math.abs(stats.saleTrend).toFixed(1)}%
                            </div>
                        )}
                    </div>

                    {/* Precio Medio Renta */}
                    <div className="bg-white/10 backdrop-blur rounded-lg p-4">
                        <div className="text-xs text-blue-200 uppercase tracking-wider mb-1">
                            Precio Promedio Renta
                        </div>
                        <div className="text-2xl md:text-3xl font-bold">
                            {formatPriceCompact(stats.avgRentPrice)}
                            <span className="text-sm font-normal text-blue-200"> /mes</span>
                        </div>
                        {stats.rentTrend !== 0 && (
                            <div className={`text-sm mt-1 flex items-center gap-1 ${stats.rentTrend > 0 ? 'text-emerald-300' : 'text-red-300'}`}>
                                {stats.rentTrend > 0 ? '▲' : '▼'} {Math.abs(stats.rentTrend).toFixed(1)}%
                            </div>
                        )}
                    </div>

                    {/* Total de Propiedades */}
                    <div className="bg-white/10 backdrop-blur rounded-lg p-4">
                        <div className="text-xs text-blue-200 uppercase tracking-wider mb-1">
                            Total Propiedades Activas
                        </div>
                        <div className="text-2xl md:text-3xl font-bold">
                            {stats.totalActive.toLocaleString()}
                        </div>
                    </div>

                    {/* Tendencia */}
                    <div className="bg-white/10 backdrop-blur rounded-lg p-4">
                        <div className="text-xs text-blue-200 uppercase tracking-wider mb-1">
                            Tendencia 30 Días
                        </div>
                        <div className={`text-2xl md:text-3xl font-bold flex items-center gap-1 ${stats.saleTrend > 0 ? 'text-emerald-300' : stats.saleTrend < 0 ? 'text-red-300' : ''}`}>
                            {stats.saleTrend > 0 ? '▲' : stats.saleTrend < 0 ? '▼' : '—'} {Math.abs(stats.saleTrend).toFixed(1)}%
                        </div>
                        <div className="text-xs text-blue-200 mt-1">vs mes anterior</div>
                    </div>
                </div>
            </div>

            {/* Rankings Section */}
            <div className="bg-gradient-to-r from-slate-700 to-slate-800 rounded-xl p-6 text-white">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    {/* Zonas Más Caras (por precio promedio) */}
                    <div>
                        <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-1">
                            Zonas Más Caras
                        </h3>
                        <p className="text-xs text-slate-400 mb-3">Por precio promedio de venta</p>
                        <div className="space-y-2">
                            {topExpensive.slice(0, 3).map((item, idx) => (
                                <Link
                                    key={idx}
                                    href={`/${departamentoToSlug(item.name)}`}
                                    className="flex items-center justify-between hover:bg-white/10 rounded-lg px-2 py-1.5 -mx-2 transition-colors cursor-pointer"
                                >
                                    <span className="text-white flex items-center gap-2">
                                        <span className="text-slate-400 text-sm">{idx + 1}.</span>
                                        {item.name}
                                    </span>
                                    <span className="font-semibold text-emerald-400">
                                        {formatPriceCompact(item.price)}
                                    </span>
                                </Link>
                            ))}
                        </div>
                    </div>

                    {/* Zonas Más Baratas (por precio promedio) */}
                    <div>
                        <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-1">
                            Zonas Más Económicas
                        </h3>
                        <p className="text-xs text-slate-400 mb-3">Por precio promedio de venta</p>
                        <div className="space-y-2">
                            {topCheap.slice(0, 3).map((item, idx) => (
                                <Link
                                    key={idx}
                                    href={`/${departamentoToSlug(item.name)}`}
                                    className="flex items-center justify-between hover:bg-white/10 rounded-lg px-2 py-1.5 -mx-2 transition-colors cursor-pointer"
                                >
                                    <span className="text-white flex items-center gap-2">
                                        <span className="text-slate-400 text-sm">{idx + 1}.</span>
                                        {item.name}
                                    </span>
                                    <span className="font-semibold text-blue-400">
                                        {formatPriceCompact(item.price)}
                                    </span>
                                </Link>
                            ))}
                        </div>
                    </div>

                    {/* Mayor Dinámica (más propiedades activas) */}
                    <div>
                        <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-1">
                            Mayor Oferta
                        </h3>
                        <p className="text-xs text-slate-400 mb-3">Más propiedades activas</p>
                        <div className="space-y-2">
                            {topActive.slice(0, 3).map((item, idx) => (
                                <Link
                                    key={idx}
                                    href={`/${departamentoToSlug(item.name)}`}
                                    className="flex items-center justify-between hover:bg-white/10 rounded-lg px-2 py-1.5 -mx-2 transition-colors cursor-pointer"
                                >
                                    <span className="text-white flex items-center gap-2">
                                        <span className="text-slate-400 text-sm">{idx + 1}.</span>
                                        {item.name}
                                    </span>
                                    <span className="font-semibold text-amber-400 flex items-center gap-1">
                                        {item.count} propiedades
                                    </span>
                                </Link>
                            ))}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
