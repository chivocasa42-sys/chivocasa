import { NextResponse } from 'next/server';

// In-memory cache for department stats (avoids re-querying Supabase on every 30s poll)
let memCache: { data: unknown; ts: number } | null = null;
const MEM_CACHE_TTL = 30_000; // 30 seconds

// Tipos para la vista materializada
export interface DepartmentStats {
    departamento: string;
    listing_type: string;
    min_price: number;
    max_price: number;
    avg_price: number;
    count: number;
}

export async function GET() {
    try {
        // Return cached response if fresh
        if (memCache && Date.now() - memCache.ts < MEM_CACHE_TTL) {
            return NextResponse.json(memCache.data, {
                headers: { 'X-Cache': 'HIT', 'Cache-Control': 'public, max-age=30, stale-while-revalidate=60' },
            });
        }

        const url = `${process.env.SUPABASE_URL}/rest/v1/mv_sd_depto_stats?select=*&order=count.desc`;

        const res = await fetch(url, {
            headers: {
                'apikey': process.env.SUPABASE_SERVICE_KEY!,
                'Authorization': `Bearer ${process.env.SUPABASE_SERVICE_KEY!}`
            },
            next: { revalidate: 300 } // Cache for 5 minutes
        });

        if (!res.ok) {
            throw new Error(`Supabase error: ${res.status}`);
        }

        const data: DepartmentStats[] = await res.json();

        // Agrupar por departamento (combinar sale y rent)
        const grouped: Record<string, {
            departamento: string;
            sale: { count: number; min: number; max: number; avg: number } | null;
            rent: { count: number; min: number; max: number; avg: number } | null;
            total_count: number;
        }> = {};

        data.forEach(row => {
            if (!grouped[row.departamento]) {
                grouped[row.departamento] = {
                    departamento: row.departamento,
                    sale: null,
                    rent: null,
                    total_count: 0
                };
            }

            const stats = {
                count: row.count,
                min: row.min_price,
                max: row.max_price,
                avg: row.avg_price
            };

            if (row.listing_type === 'sale') {
                grouped[row.departamento].sale = stats;
            } else if (row.listing_type === 'rent') {
                grouped[row.departamento].rent = stats;
            }

            grouped[row.departamento].total_count += row.count;
        });

        // Convertir a array y ordenar por total_count
        const result = Object.values(grouped).sort((a, b) => b.total_count - a.total_count);

        // Update in-memory cache
        memCache = { data: result, ts: Date.now() };

        return NextResponse.json(result, {
            headers: {
                'X-Cache': 'MISS',
                'Cache-Control': 'public, s-maxage=60, max-age=30, stale-while-revalidate=300',
            },
        });
    } catch (error) {
        console.error('Error fetching department stats:', error);
        return NextResponse.json({ error: 'Failed to fetch department stats' }, { status: 500 });
    }
}
