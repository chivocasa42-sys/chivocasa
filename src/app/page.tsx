import './pages.css';
import Navbar from '@/components/Navbar';
import HeroSection from '@/components/HeroSection';
import HomeToolsSection from '@/components/HomeToolsSection';
import KPIStrip from '@/components/KPIStrip';
import { fetchDepartmentStats } from '@/lib/fetchDepartmentStats';

function buildKpiStats(departments: Awaited<ReturnType<typeof fetchDepartmentStats>>) {
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
}

export default async function Home() {
  const departments = await fetchDepartmentStats();
  const kpiStats = buildKpiStats(departments);

  return (
    <>
      <Navbar totalListings={kpiStats.totalActive} />

      <HeroSection variant="cta" />

      <main className="container mx-auto px-4 max-w-7xl">
        <KPIStrip
          stats={kpiStats}
          variant="home"
          className="-mt-5 sm:-mt-7 lg:-mt-8 relative z-20 mb-10 lg:mb-12"
        />

        <HomeToolsSection />
      </main>
    </>
  );
}
