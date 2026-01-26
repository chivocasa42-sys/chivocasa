'use client';

import { Insights } from '@/types/biStats';

interface InsightsPanelProps {
    insights: Insights;
}

export default function InsightsPanel({ insights }: InsightsPanelProps) {
    const { top3_active_7d } = insights;

    // No mostrar si no hay actividad
    if (top3_active_7d.length === 0) {
        return null;
    }

    // Calcular el máximo para las barras proporcionales
    const maxValue = Math.max(...top3_active_7d.map(i => i.value), 1);

    return (
        <div className="mt-10 mb-6">
            {/* Header */}
            <div className="flex items-center gap-2 mb-4">
                <h3 className="text-lg font-bold text-slate-800 uppercase tracking-wide">
                    Zonas con más movimiento
                </h3>
            </div>

            {/* Top 3 con barras */}
            <div className="bg-white rounded-xl p-5 shadow-sm border border-slate-200">
                <div className="space-y-4">
                    {top3_active_7d.map((item, idx) => (
                        <div key={idx} className="flex items-center gap-4">
                            {/* Número */}
                            <span className="text-slate-400 font-medium w-4">
                                {idx + 1}.
                            </span>

                            {/* Nombre y departamento */}
                            <div className="flex-1 min-w-0">
                                <div className="text-sm font-medium text-slate-800 truncate">
                                    {item.municipio}
                                </div>
                                <div className="text-xs text-slate-400">
                                    {item.departamento}
                                </div>
                            </div>

                            {/* Barra proporcional */}
                            <div className="w-24 h-2 bg-slate-100 rounded-full overflow-hidden">
                                <div
                                    className="h-full bg-rose-400 rounded-full transition-all"
                                    style={{ width: `${(item.value / maxValue) * 100}%` }}
                                />
                            </div>

                            {/* Valor */}
                            <span className="text-sm font-medium text-emerald-600 w-16 text-right">
                                +{item.value} nuevos
                            </span>
                        </div>
                    ))}
                </div>

                {/* Footer explicativo */}
                <div className="mt-4 pt-4 border-t border-slate-100">
                    <p className="text-xs text-slate-400">
                        Basado en listings agregados en los últimos 7 días.
                    </p>
                </div>
            </div>
        </div>
    );
}
