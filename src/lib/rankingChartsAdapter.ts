// Adapter: transforma los rankings existentes (page.tsx useMemo) → datapoints para ECharts
// NO recalcula nada — solo mapea la estructura existente

import { departamentoToSlug } from '@/lib/slugify';

export interface RankingItem {
  name: string;
  value: number;
}

export interface ChartDataPoint {
  label: string;
  y: number;
  id: string; // slug for navigation
  indexLabel: string; // formatted value shown on the bar
}

export function formatPriceCompact(price: number): string {
  if (!price || price === 0) return 'N/A';
  if (price >= 1000000) return '$' + (price / 1000000).toFixed(1) + 'M';
  if (price >= 1000) return '$' + Math.round(price / 1000) + 'K';
  return '$' + Math.round(price).toLocaleString();
}

export function toExpensiveDataPoints(items: RankingItem[]): ChartDataPoint[] {
  return items.slice(0, 5).reverse().map(item => ({
    label: item.name,
    y: item.value,
    id: departamentoToSlug(item.name),
    indexLabel: formatPriceCompact(item.value),
  }));
}

export function toCheapDataPoints(items: RankingItem[]): ChartDataPoint[] {
  return items.slice(0, 5).reverse().map(item => ({
    label: item.name,
    y: item.value,
    id: departamentoToSlug(item.name),
    indexLabel: formatPriceCompact(item.value),
  }));
}

export function toActiveDataPoints(items: RankingItem[]): ChartDataPoint[] {
  return items.slice(0, 5).map(item => ({
    label: item.name,
    y: item.value,
    id: departamentoToSlug(item.name),
    indexLabel: item.value.toLocaleString(),
  }));
}

// Compute rankings from raw department data — same logic as page.tsx lines 98-117
export interface DepartmentStats {
  departamento: string;
  sale: { count: number; min: number; max: number; avg: number } | null;
  rent: { count: number; min: number; max: number; avg: number } | null;
  total_count: number;
}

export function computeRankings(departments: DepartmentStats[]) {
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

  const topActive = [...departments]
    .sort((a, b) => b.total_count - a.total_count)
    .slice(0, 3)
    .map(d => ({ name: d.departamento, value: d.total_count }));

  return { topExpensive, topCheap, topActive };
}
