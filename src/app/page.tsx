'use client';

import './pages.css';
import { useEffect, useMemo, useState } from 'react';
import Navbar from '@/components/Navbar';
import HeroSection from '@/components/HeroSection';
import HomeToolsSection from '@/components/HomeToolsSection';
import KPIStrip from '@/components/KPIStrip';
import type { DepartmentStats } from '@/lib/departmentStats';

export default function Home() {
  const [departments, setDepartments] = useState<DepartmentStats[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
        setError('No pudimos cargar los datos. Verifica tu conexion e intenta de nuevo.');
        console.error(err);
      } finally {
        setIsLoading(false);
      }
    }

    fetchStats();
  }, []);

  const kpiStats = useMemo(() => {
    let sumSalePrice = 0;
    let sumRentPrice = 0;
    let saleCount = 0;
    let rentCount = 0;
    let totalActive = 0;

    departments.forEach((dept) => {
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

      <HeroSection variant="cta" />

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
            <KPIStrip
              stats={kpiStats}
              variant="home"
              className="-mt-5 sm:-mt-7 lg:-mt-8 relative z-20 mb-10 lg:mb-12"
            />

            <HomeToolsSection />
          </>
        )}
      </main>
    </>
  );
}
