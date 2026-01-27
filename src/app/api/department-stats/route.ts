import { NextResponse } from 'next/server';

export const runtime = 'edge';

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

        return NextResponse.json(result);
    } catch (error) {
        console.error('Error fetching department stats:', error);
        return NextResponse.json({ error: 'Failed to fetch department stats' }, { status: 500 });
    }
}
