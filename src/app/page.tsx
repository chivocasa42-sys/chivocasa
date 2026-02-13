'use client';

import './pages.css';
import { useState, useEffect, useMemo, useCallback } from 'react';
import dynamic from 'next/dynamic';
import Navbar from '@/components/Navbar';
import HeroSection from '@/components/HeroSection';
import HomeHeader from '@/components/HomeHeader';
import DepartmentCard from '@/components/DepartmentCard';
import SectionHeader from '@/components/SectionHeader';
import { departamentoToSlug } from '@/lib/slugify';

// Dynamic imports — keep heavy components (Leaflet, ECharts) out of initial bundle
const MapExplorer = dynamic(() => import('@/components/MapExplorer'), {
  ssr: false,
  loading: () => (
    <div className="w-full rounded-2xl border border-[#e2e8f0] bg-[var(--bg-card)] overflow-hidden mb-8" style={{ height: '500px' }}>
      <div className="skeleton-pulse w-full h-full" />
    </div>
  ),
});



interface HeroLocation {
  lat: number;
  lng: number;
  name: string;
}

interface DepartmentStats {
  departamento: string;
  sale: { count: number; min: number; max: number; avg: number } | null;
  rent: { count: number; min: number; max: number; avg: number } | null;
  total_count: number;
}

type PeriodType = '7d' | '30d' | '90d';
type ViewType = 'all' | 'sale' | 'rent';
type OrderType = 'activity' | 'price' | 'variation';

export default function Home() {
  const [departments, setDepartments] = useState<DepartmentStats[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Controles
  const [period, setPeriod] = useState<PeriodType>('30d');
  const [view, setView] = useState<ViewType>('all');
  const [orderBy, setOrderBy] = useState<OrderType>('activity');

  // Hero → MapExplorer bridge
  const [heroLocation, setHeroLocation] = useState<HeroLocation | null>(null);
  const handleHeroLocationSelect = useCallback((lat: number, lng: number, name: string) => {
    setHeroLocation({ lat, lng, name });
  }, []);

  useEffect(() => {
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
  }, []);

  // Calcular totalActive para el Navbar
  const totalActive = useMemo(() => {
    return departments.reduce((sum, dept) => sum + dept.total_count, 0);
  }, [departments]);

  // Filtrar y ordenar departamentos
  const filteredDepartments = useMemo(() => {
    let filtered = departments.filter(d => d.total_count > 0);

    // Filtrar por vista
    if (view === 'sale') {
      filtered = filtered.filter(d => d.sale && d.sale.count > 0);
    } else if (view === 'rent') {
      filtered = filtered.filter(d => d.rent && d.rent.count > 0);
    }
    // 'all' shows everything — no additional filtering

    // Ordenar
    switch (orderBy) {
      case 'activity':
        filtered.sort((a, b) => b.total_count - a.total_count);
        break;
      case 'price':
        filtered.sort((a, b) => (b.sale?.avg || 0) - (a.sale?.avg || 0));
        break;
      case 'variation':
        // Ordenar por precio (simulado sin data histórica)
        filtered.sort((a, b) => b.total_count - a.total_count);
        break;
    }

    return filtered;
  }, [departments, view, orderBy]);

  // Obtener stats para mostrar según view
  const getDisplayStats = (dept: DepartmentStats) => {
    if (view === 'sale' && dept.sale) {
      return { median: dept.sale.avg, min: dept.sale.min, max: dept.sale.max };
    }
    if (view === 'rent' && dept.rent) {
      return { median: dept.rent.avg, min: dept.rent.min, max: dept.rent.max };
    }
    // 'all': weighted average of sale and rent prices, combined min/max
    const saleAvg = dept.sale?.avg || 0;
    const rentAvg = dept.rent?.avg || 0;
    const saleCount = dept.sale?.count || 0;
    const rentCount = dept.rent?.count || 0;
    const totalCount = saleCount + rentCount;
    const weightedMedian = totalCount > 0
      ? (saleAvg * saleCount + rentAvg * rentCount) / totalCount
      : 0;
    return {
      median: weightedMedian || saleAvg || rentAvg,
      min: Math.min(dept.sale?.min || Infinity, dept.rent?.min || Infinity) === Infinity ? 0 : Math.min(dept.sale?.min || Infinity, dept.rent?.min || Infinity),
      max: Math.max(dept.sale?.max || 0, dept.rent?.max || 0)
    };
  };

  return (
    <>
      <Navbar
        totalListings={totalActive}
        onRefresh={() => window.location.reload()}
      />

      {/* Hero Section */}
      <HeroSection onLocationSelect={handleHeroLocationSelect} />

      <main className="container mx-auto px-4 max-w-7xl">
        {/* Loading / Error / Content */}
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


            {/* Map Explorer - Interactive location search */}
            <div id="mapa" className="scroll-mt-20">
              <MapExplorer externalLocation={heroLocation} />
            </div>

            {/* Departamentos Grid */}
            <div id="departamentos" className="mb-8 scroll-mt-24">
              <SectionHeader
                title={['Precios y oferta', 'por departamento']}
                subtitle="Comparativo de precios y oferta inmobiliaria para decidir dónde conviene buscar en El Salvador"
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
            </div>



            {/* No Clasificado - solo mostrar si hay data */}
            {/* TODO: Agregar cuando tengamos el endpoint */}
          </>
        )}
      </main>
    </>
  );
}
