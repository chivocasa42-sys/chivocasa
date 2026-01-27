import { NextResponse } from 'next/server';
import { slugToDepartamento, isValidDepartamentoSlug } from '@/lib/slugify';



export interface TopScoredListing {
    external_id: number;
    title: string;
    location: Record<string, unknown>;
    departamento: string;
    listing_type: 'sale' | 'rent';
    price: number;
    mt2: number;
    bedrooms: number;
    bathrooms: number;
    price_per_m2: number;
    score: number;
    url: string;
}

export async function GET(
    request: Request,
    { params }: { params: Promise<{ slug: string }> }
) {
    try {
        const { slug } = await params;
        const { searchParams } = new URL(request.url);
        // type: 'sale', 'rent', 'all' (or null for both)
        const listingType = searchParams.get('type') || 'all';
        const topPerType = parseInt(searchParams.get('limit') || '10');

        if (!isValidDepartamentoSlug(slug)) {
            return NextResponse.json({ error: 'Departamento no válido' }, { status: 404 });
        }

        const departamento = slugToDepartamento(slug);

        // Llamar a la función RPC get_top_scored_listings (actualizada)
        const url = `${process.env.SUPABASE_URL}/rest/v1/rpc/get_top_scored_listings`;

        console.time(`[PERF] /api/department/${slug}/top-scored - Supabase RPC call`);
        const res = await fetch(url, {
            method: 'POST',
            headers: {
                'apikey': process.env.SUPABASE_SERVICE_KEY!,
                'Authorization': `Bearer ${process.env.SUPABASE_SERVICE_KEY!}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                p_departamento: departamento,
                p_listing_type: listingType === 'all' ? null : listingType,
                p_top_per_type: topPerType
            }),
            next: { revalidate: 300 }
        });
        console.timeEnd(`[PERF] /api/department/${slug}/top-scored - Supabase RPC call`);

        if (!res.ok) {
            const errorText = await res.text();
            console.error('Supabase RPC error:', errorText);
            throw new Error(`Supabase error: ${res.status}`);
        }

        console.time(`[PERF] /api/department/${slug}/top-scored - JSON parse`);
        const data: TopScoredListing[] = await res.json();
        console.timeEnd(`[PERF] /api/department/${slug}/top-scored - JSON parse`);

        // Separar por tipo
        const saleListings = data.filter(l => l.listing_type === 'sale');
        const rentListings = data.filter(l => l.listing_type === 'rent');

        return NextResponse.json({
            departamento,
            sale: saleListings,
            rent: rentListings,
            all: data
        });
    } catch (error) {
        console.error('Error fetching top scored listings:', error);
        return NextResponse.json({ error: 'Failed to fetch' }, { status: 500 });
    }
}
