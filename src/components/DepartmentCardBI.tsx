'use client';

import { DepartmentBIStats } from '@/types/biStats';
import { formatPrice } from '@/lib/biCalculations';

interface DepartmentCardBIProps {
    stats: DepartmentBIStats;
    filterType: 'all' | 'sale' | 'rent';
    onClick: () => void;
}

// Formatear precio compacto (K para miles)
function formatPriceCompact(price: number): string {
    if (!price || price === 0) return 'N/A';
    if (price >= 1000000) {
        return '$' + (price / 1000000).toFixed(1) + 'M';
    }
    if (price >= 1000) {
        return '$' + Math.round(price / 1000) + 'K';
    }
    return '$' + price.toLocaleString();
}

export default function DepartmentCardBI({ stats, filterType, onClick }: DepartmentCardBIProps) {
    return (
        <div
            className="bg-white rounded-xl shadow-sm border border-slate-200 hover:shadow-md hover:border-rose-300 hover:scale-[1.01] transition-all duration-200 cursor-pointer flex flex-col"
            onClick={onClick}
        >
            {/* Header */}
            <div className="p-5 pb-3">
                <div className="flex justify-between items-start mb-2">
                    <h3 className="font-semibold text-lg text-slate-800 flex items-center gap-2">
                        {stats.departamento}
                    </h3>
                    <span className="bg-slate-600 text-white text-xs font-bold px-2 py-1 rounded-full min-w-[32px] text-center">
                        {stats.count_active}
                    </span>
                </div>

                {/* Municipios */}
                <div className="text-sm text-slate-500 flex items-center gap-1.5">
                    <span>🏘️</span>
                    <span>{stats.municipios_con_actividad} municipio{stats.municipios_con_actividad !== 1 ? 's' : ''}</span>
                </div>
            </div>

            {/* Precio Principal */}
            <div className="px-5 py-4 border-t border-slate-100">
                <div className="text-3xl font-bold text-rose-500">
                    {formatPrice(stats.median_price)}
                </div>
            </div>

            {/* Rango como Pill */}
            <div className="px-5 pb-3">
                <span className="inline-flex items-center gap-1.5 bg-slate-100 text-slate-600 text-xs font-medium px-3 py-1.5 rounded-full">
                    {formatPriceCompact(stats.p25_price)} → {formatPriceCompact(stats.p75_price)}
                </span>
            </div>

            {/* Actividad como Chip */}
            <div className="px-5 pb-4">
                <span className={`inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full ${stats.new_7d > 0
                        ? 'bg-emerald-100 text-emerald-700'
                        : 'bg-slate-100 text-slate-500'
                    }`}>
                    {stats.new_7d > 0 ? (
                        <>
                            <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 16 16">
                                <path fillRule="evenodd" d="M8 12a.5.5 0 0 0 .5-.5V5.707l2.146 2.147a.5.5 0 0 0 .708-.708l-3-3a.5.5 0 0 0-.708 0l-3 3a.5.5 0 1 0 .708.708L7.5 5.707V11.5a.5.5 0 0 0 .5.5z" />
                            </svg>
                            +{stats.new_7d} esta semana
                        </>
                    ) : (
                        'Sin nuevos'
                    )}
                </span>
            </div>

            {/* CTA */}
            <div className="px-5 py-3 border-t border-slate-100 mt-auto bg-slate-50 rounded-b-xl">
                <div className="text-sm text-rose-500 font-medium flex items-center justify-end gap-1">
                    Ver municipios
                    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 16 16">
                        <path fillRule="evenodd" d="M4.646 1.646a.5.5 0 0 1 .708 0l6 6a.5.5 0 0 1 0 .708l-6 6a.5.5 0 0 1-.708-.708L10.293 8 4.646 2.354a.5.5 0 0 1 0-.708z" />
                    </svg>
                </div>
            </div>
        </div>
    );
}
