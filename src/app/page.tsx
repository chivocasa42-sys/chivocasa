'use client';

import { useState, useEffect, useMemo } from 'react';
import Navbar from '@/components/Navbar';
import HeroSection from '@/components/HeroSection';
import FeatureCards from '@/components/FeatureCards';
import HomeHeader from '@/components/HomeHeader';
import KPIStrip from '@/components/KPIStrip';
import RankingsSection from '@/components/RankingsSection';
import TrendsSection from '@/components/TrendsSection';
import DepartmentCard from '@/components/DepartmentCard';
import SectionHeader from '@/components/SectionHeader';
import { departamentoToSlug } from '@/lib/slugify';
import Link from 'next/link';

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
    // All: usar venta si existe
    const saleAvg = dept.sale?.avg || 0;
    return {
      median: saleAvg,
      min: dept.sale?.min || dept.rent?.min || 0,
      max: dept.sale?.max || dept.rent?.max || 0
    };
  };

  return (
    <>
      <Navbar
        totalListings={kpiStats.totalActive}
        onRefresh={() => window.location.reload()}
      />

      {/* Hero Section - Earnwave Style */}
      <HeroSection />

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
            {/* KPI Strip */}
            <KPIStrip stats={kpiStats} />

            {/* Rankings */}
            <div id="rankings">
              <RankingsSection
                topExpensive={rankings.topExpensive}
                topCheap={rankings.topCheap}
                topActive={rankings.topActive}
              />
            </div>

            {/* Tendencias */}
            <div id="tendencias">
              <TrendsSection
                departmentData={departments}
                period={period}
              />
            </div>

            {/* Departamentos Grid */}
            <div id="departamentos" className="mb-8 scroll-mt-24">
              <SectionHeader
                title={['Panorama', 'por departamento']}
                subtitle="Precio típico en venta (P50-P85) y nuevos en 7 días por región"
                actionLabel="Ver detalles"
                actionHref="#"
              />

              <div className="mb-8">
                <HomeHeader
                  period={period}
                  view={view}
                  orderBy={orderBy}
                  onPeriodChange={setPeriod}
                  onViewChange={setView}
                  onOrderChange={setOrderBy}
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
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
