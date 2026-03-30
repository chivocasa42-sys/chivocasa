'use client';

import { useEffect, useMemo, useState } from 'react';
import Navbar from '@/components/Navbar';
import HomeHeader from '@/components/HomeHeader';
import DepartmentCard from '@/components/DepartmentCard';
import SectionHeader from '@/components/SectionHeader';
import { departamentoToSlug } from '@/lib/slugify';
import type { DepartmentStats } from '@/lib/departmentStats';

type ViewType = 'all' | 'sale' | 'rent';
type OrderType = 'activity' | 'price' | 'variation';

interface DepartmentMarketClientProps {
    initialData?: DepartmentStats[];
}

export default function DepartmentMarketClient({ initialData }: DepartmentMarketClientProps) {
    const [departments, setDepartments] = useState<DepartmentStats[]>(initialData ?? []);
    const [isLoading, setIsLoading] = useState(!initialData || initialData.length === 0);
    const [error, setError] = useState<string | null>(null);
    const [view, setView] = useState<ViewType>('all');
    const orderBy: OrderType = 'activity';

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

    const filteredDepartments = useMemo(() => {
        let filtered = departments.filter((d) => d.total_count > 0);

        if (view === 'sale') {
            filtered = filtered.filter((d) => d.sale && d.sale.count > 0);
        } else if (view === 'rent') {
            filtered = filtered.filter((d) => d.rent && d.rent.count > 0);
        }

        switch (orderBy) {
            case 'activity':
                filtered.sort((a, b) => b.total_count - a.total_count);
                break;
            case 'price':
                filtered.sort((a, b) => (b.sale?.avg || 0) - (a.sale?.avg || 0));
                break;
            case 'variation':
                filtered.sort((a, b) => b.total_count - a.total_count);
                break;
        }

        return filtered;
    }, [departments, view, orderBy]);

    const getDisplayStats = (dept: DepartmentStats) => {
        if (view === 'sale' && dept.sale) {
            return { median: dept.sale.avg, min: dept.sale.min, max: dept.sale.max };
        }

        if (view === 'rent' && dept.rent) {
            return { median: dept.rent.avg, min: dept.rent.min, max: dept.rent.max };
        }

        const saleAvg = dept.sale?.avg || 0;
        const rentAvg = dept.rent?.avg || 0;
        const saleCount = dept.sale?.count || 0;
        const rentCount = dept.rent?.count || 0;
        const totalCount = saleCount + rentCount;
        const weightedMedian =
            totalCount > 0 ? (saleAvg * saleCount + rentAvg * rentCount) / totalCount : 0;

        return {
            median: weightedMedian || saleAvg || rentAvg,
            min:
                Math.min(dept.sale?.min || Infinity, dept.rent?.min || Infinity) === Infinity
                    ? 0
                    : Math.min(dept.sale?.min || Infinity, dept.rent?.min || Infinity),
            max: Math.max(dept.sale?.max || 0, dept.rent?.max || 0),
        };
    };

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
                        <SectionHeader
                            title={['Precios y oferta', 'por departamento']}
                            subtitle="Comparativo de precios y oferta inmobiliaria para decidir donde conviene buscar en El Salvador."
                            asH1
                        />

                        <div className="mb-8">
                            <HomeHeader
                                view={view}
                                onViewChange={setView}
                            />
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3 sm:gap-4 lg:gap-5">
                            {filteredDepartments.map((dept) => {
                                const stats = getDisplayStats(dept);

                                return (
                                    <DepartmentCard
                                        key={dept.departamento}
                                        departamento={dept.departamento}
                                        totalCount={dept.total_count}
                                        saleCount={dept.sale?.count}
                                        rentCount={dept.rent?.count}
                                        medianPrice={stats.median}
                                        priceRangeMin={stats.min}
                                        priceRangeMax={stats.max}
                                        slug={departamentoToSlug(dept.departamento)}
                                        activeFilter={view}
                                    />
                                );
                            })}
                        </div>
                    </section>
                )}
            </main>
        </>
    );
}
