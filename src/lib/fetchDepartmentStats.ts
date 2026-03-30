import 'server-only';

import { unstable_cache } from 'next/cache';
import type { DepartmentStats, DepartmentStatsRow } from './departmentStats';

async function _fetchDepartmentStats(): Promise<DepartmentStats[]> {
    try {
        const url = `${process.env.SUPABASE_URL}/rest/v1/mv_sd_depto_stats?select=*&order=count.desc`;
        const res = await fetch(url, {
            headers: {
                apikey: process.env.SUPABASE_SERVICE_KEY!,
                Authorization: `Bearer ${process.env.SUPABASE_SERVICE_KEY!}`,
            },
            next: { revalidate: 300 },
        });

        if (!res.ok) return [];

        const data: DepartmentStatsRow[] = await res.json();

        const grouped: Record<string, DepartmentStats> = {};

        data.forEach((row) => {
            if (!grouped[row.departamento]) {
                grouped[row.departamento] = {
                    departamento: row.departamento,
                    sale: null,
                    rent: null,
                    total_count: 0,
                };
            }

            const stats = {
                count: row.count,
                min: row.min_price,
                max: row.max_price,
                avg: row.avg_price,
            };

            if (row.listing_type === 'sale') {
                grouped[row.departamento].sale = stats;
            } else if (row.listing_type === 'rent') {
                grouped[row.departamento].rent = stats;
            }

            grouped[row.departamento].total_count += row.count;
        });

        return Object.values(grouped).sort((a, b) => b.total_count - a.total_count);
    } catch {
        return [];
    }
}

export const fetchDepartmentStats = unstable_cache(
    _fetchDepartmentStats,
    ['dept-stats-shared'],
    { revalidate: 300, tags: ['dept-stats'] }
);
