'use client';

import { useState, useEffect, useMemo } from 'react';
import dynamic from 'next/dynamic';
import Navbar from '@/components/Navbar';
import HomeHeader from '@/components/HomeHeader';
import KPIStrip from '@/components/KPIStrip';
import SectionHeader from '@/components/SectionHeader';

// Dynamic import — keep ECharts out of initial bundle
const MarketRankingCharts = dynamic(() => import('@/components/MarketRankingCharts'), {
    ssr: false,
    loading: () => (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {[0, 1, 2].map((i) => (
                <div key={i} className="ranking-chart-skeleton">
                    <div className="skeleton-title" />
                    <div className="skeleton-subtitle" />
                    <div className="skeleton-bars">
                        <div className="skeleton-bar" style={{ width: '90%' }} />
                        <div className="skeleton-bar" style={{ width: '65%' }} />
                        <div className="skeleton-bar" style={{ width: '45%' }} />
                    </div>
                </div>
            ))}
        </div>
    ),
});

interface DepartmentStats {
    departamento: string;
    sale: { count: number; min: number; max: number; avg: number } | null;
    rent: { count: number; min: number; max: number; avg: number } | null;
    total_count: number;
}

type ViewType = 'all' | 'sale' | 'rent';

interface TendenciasClientProps {
    initialData?: DepartmentStats[];
}

export default function TendenciasClient({ initialData }: TendenciasClientProps) {
    const [departments, setDepartments] = useState<DepartmentStats[]>(initialData ?? []);
    const [isLoading, setIsLoading] = useState(!initialData || initialData.length === 0);
    const [error, setError] = useState<string | null>(null);
    const [view, setView] = useState<ViewType>('all');

    useEffect(() => {
        // Skip fetch if we already have server-provided data
        if (initialData && initialData.length > 0) return;

        async function fetchStats() {
            setIsLoading(true);
            setError(null);
            try {
                const res = await fetch('/api/department-stats');
                if (!res.ok) throw new Error('Failed to fetch');
                const data = await res.json();
                setDepartments(data);
            } catch (err) {
                setError('No pudimos cargar los datos. Verificá tu conexión e intentá de nuevo.');
                console.error(err);
            } finally {
                setIsLoading(false);
            }
        }
        fetchStats();
    }, [initialData]);

    // Calcular KPI stats
    const kpiStats = useMemo(() => {
        let sumSalePrice = 0, sumRentPrice = 0;
        let saleCount = 0, rentCount = 0;
        let totalActive = 0;

        departments.forEach(dept => {
            if (dept.sale) {
                sumSalePrice += dept.sale.avg * dept.sale.count;
                saleCount += dept.sale.count;
            }
            if (dept.rent) {
                sumRentPrice += dept.rent.avg * dept.rent.count;
                rentCount += dept.rent.count;
            }
            totalActive += dept.total_count;
        });

        return {
            medianSale: saleCount > 0 ? sumSalePrice / saleCount : 0,
            medianRent: rentCount > 0 ? sumRentPrice / rentCount : 0,
            totalActive,
            new7d: Math.round(totalActive * 0.05),
            saleTrend: 2.3,
            rentTrend: 1.8,
        };
    }, [departments]);

    return (
        <>
            <Navbar
                totalListings={kpiStats.totalActive}
                onRefresh={() => window.location.reload()}
            />

            <main className="container mx-auto px-4 max-w-7xl">
                {isLoading ? (
                    <div className="flex flex-col justify-center items-center min-h-[400px] gap-4">
                        <div className="spinner"></div>
                        <p className="text-[var(--text-secondary)]">Cargando datos del mercado...</p>
                    </div>
                ) : error ? (
                    <div className="card-float p-8 text-center">
                        <p className="text-[var(--text-secondary)] mb-4">{error}</p>
                        <button
                            onClick={() => window.location.reload()}
                            className="btn-primary"
                        >
                            Reintentar
                        </button>
                    </div>
                ) : (


                    <>
                        {/* ══════════════════════════════════════════════
                            SECTION 1 — Panorama (KPI cards)
                           ══════════════════════════════════════════════ */}
                        <section className="pt-10 pb-10">
                            <SectionHeader
                                title={['Panorama del mercado inmobiliario', 'en El Salvador']}
                                subtitle="Precios promedio, rentas mensuales y nuevas oportunidades inmobiliarias, actualizadas para ayudarte a tomar decisiones con mayor confianza."
                                asH1
                            />

                            {/* KPI Strip */}
                            <KPIStrip stats={kpiStats} />

                        </section>

                        {/* ── Subtle divider between sections ── */}
                        <hr className="border-t border-slate-200/70 my-0" />

                        {/* ══════════════════════════════════════════════
                            SECTION 2 — Ranking Charts
                           ══════════════════════════════════════════════ */}
                        <section className="pt-10 pb-12">
                            <div id="rankings" className="scroll-mt-20">
                                <MarketRankingCharts
                                    departments={departments}
                                    activeFilter={view}
                                    filterSlot={
                                        <HomeHeader
                                            view={view}
                                            onViewChange={setView}
                                        />
                                    }
                                />
                            </div>
                        </section>

                        {/* Disclaimer */}
                        <p className="text-xs md:text-sm text-[var(--text-muted)] text-center mt-1 mb-10 max-w-4xl mx-auto italic opacity-75">
                            Los valores mostrados son promedios estimados y pueden variar según la zona y el tipo de propiedad.
                        </p>
                    </>
                )}
            </main>
        </>
    );
}
