'use client';

import { useState, useEffect, useMemo, useCallback } from 'react';
import dynamic from 'next/dynamic';
import Navbar from '@/components/Navbar';
import HeroSection from '@/components/HeroSection';
import FeatureCards from '@/components/FeatureCards';
import HomeHeader from '@/components/HomeHeader';
import KPIStrip from '@/components/KPIStrip';
import DepartmentCard from '@/components/DepartmentCard';
import SectionHeader from '@/components/SectionHeader';
import { departamentoToSlug } from '@/lib/slugify';
import Link from 'next/link';

// Dynamic imports — keep heavy components (Leaflet, ECharts) out of initial bundle
const MapExplorer = dynamic(() => import('@/components/MapExplorer'), {
  ssr: false,
  loading: () => (
    <div className="w-full rounded-2xl border border-[#e2e8f0] bg-[var(--bg-card)] overflow-hidden mb-8" style={{ height: '500px' }}>
      <div className="skeleton-pulse w-full h-full" />
    </div>
  ),
});

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
      new7d: Math.round(totalActive * 0.05), // Simulated
      saleTrend: 2.3,
      rentTrend: 1.8,
    };
  }, [departments]);

  // Rankings
  const rankings = useMemo(() => {
    const topExpensive = departments
      .filter(d => d.sale && d.sale.avg > 0)
      .sort((a, b) => (b.sale?.avg || 0) - (a.sale?.avg || 0))
      .slice(0, 3)
      .map(d => ({ name: d.departamento, value: d.sale?.avg || 0 }));

    const topCheap = departments
      .filter(d => d.sale && d.sale.avg > 0)
      .sort((a, b) => (a.sale?.avg || 0) - (b.sale?.avg || 0))
      .slice(0, 3)
      .map(d => ({ name: d.departamento, value: d.sale?.avg || 0 }));

    const topActive = departments
      .sort((a, b) => b.total_count - a.total_count)
      .slice(0, 3)
      .map(d => ({ name: d.departamento, value: d.total_count }));

    return { topExpensive, topCheap, topActive };
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
        totalListings={kpiStats.totalActive}
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
            {/* Market Panorama Header */}
            <div className="mb-4">
              <SectionHeader
                title={['Panorama del mercado inmobiliario', 'en El Salvador']}
                subtitle="Precios promedio, rentas mensuales y nuevas oportunidades inmobiliarias, actualizadas para ayudarte a tomar decisiones con mayor confianza."
              />
            </div>

            {/* KPI Strip */}
            <KPIStrip stats={kpiStats} />

            {/* Disclaimer — below KPIs, above Map Explorer */}
            <p className="text-xs md:text-sm text-[var(--text-muted)] text-center mt-1 mb-4 max-w-4xl mx-auto italic opacity-75">
              Los valores mostrados son promedios estimados y pueden variar según la zona y el tipo de propiedad.
            </p>

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

            {/* Rankings — CanvasJS Charts with lazy load + polling */}
            <div id="rankings" className="scroll-mt-20">
              <MarketRankingCharts departments={departments} activeFilter={view} />
            </div>

            {/* Duplicate filter buttons below charts for convenience */}
            <div className="mt-6 mb-8">
              <HomeHeader
                view={view}
                onViewChange={setView}
              />
            </div>

            {/* No Clasificado - solo mostrar si hay data */}
            {/* TODO: Agregar cuando tengamos el endpoint */}
          </>
        )}
      </main>
    </>
  );
}
