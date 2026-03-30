'use client';

import { useState, useEffect, useMemo } from 'react';
import dynamic from 'next/dynamic';
import Navbar from '@/components/Navbar';
import HomeHeader from '@/components/HomeHeader';

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
                setError('No pudimos cargar los datos. Verifica tu conexion e intenta de nuevo.');
                console.error(err);
            } finally {
                setIsLoading(false);
            }
        }

        fetchStats();
    }, [initialData]);

    const totalActive = useMemo(
        () => departments.reduce((sum, dept) => sum + dept.total_count, 0),
        [departments]
    );

    return (
        <>
            <Navbar
                totalListings={totalActive}
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
                )}
            </main>
        </>
    );
}
