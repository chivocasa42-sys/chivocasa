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

export type ViewType = 'all' | 'sale' | 'rent';

// Get the relevant avg price for a department based on the active filter
function getAvgPrice(d: DepartmentStats, view: ViewType): number {
  if (view === 'sale') return d.sale?.avg || 0;
  if (view === 'rent') return d.rent?.avg || 0;
  // 'all': weighted average of sale and rent
  const saleAvg = d.sale?.avg || 0;
  const rentAvg = d.rent?.avg || 0;
  const saleCount = d.sale?.count || 0;
  const rentCount = d.rent?.count || 0;
  const total = saleCount + rentCount;
  if (total === 0) return 0;
  return (saleAvg * saleCount + rentAvg * rentCount) / total;
}

// Get the relevant listing count for a department based on the active filter
function getCount(d: DepartmentStats, view: ViewType): number {
  if (view === 'sale') return d.sale?.count || 0;
  if (view === 'rent') return d.rent?.count || 0;
  return d.total_count;
}

export function computeRankings(departments: DepartmentStats[], view: ViewType = 'all') {
  const withPrice = departments.filter(d => getAvgPrice(d, view) > 0);

  const topExpensive = [...withPrice]
    .sort((a, b) => getAvgPrice(b, view) - getAvgPrice(a, view))
    .slice(0, 3)
    .map(d => ({ name: d.departamento, value: getAvgPrice(d, view) }));

  const topCheap = [...withPrice]
    .sort((a, b) => getAvgPrice(a, view) - getAvgPrice(b, view))
    .slice(0, 3)
    .map(d => ({ name: d.departamento, value: getAvgPrice(d, view) }));

  const topActive = [...departments]
    .filter(d => getCount(d, view) > 0)
    .sort((a, b) => getCount(b, view) - getCount(a, view))
    .slice(0, 3)
    .map(d => ({ name: d.departamento, value: getCount(d, view) }));

  return { topExpensive, topCheap, topActive };
}
