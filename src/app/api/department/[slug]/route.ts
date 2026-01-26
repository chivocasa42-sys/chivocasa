import { NextResponse } from 'next/server';
import { slugToDepartamento, isValidDepartamentoSlug } from '@/lib/slugify';

const DEFAULT_LIMIT = 24;

export interface CardListing {
    external_id: number;
    title: string;
    price: number;
    listing_type: 'sale' | 'rent';
    first_image: string | null;
    bedrooms: number | null;
    bathrooms: number | null;
    area: number | null;
    municipio: string | null;
    total_count: number;
}

export async function GET(
    request: Request,
    { params }: { params: Promise<{ slug: string }> }
) {
    try {
        const { slug } = await params;
        const { searchParams } = new URL(request.url);

        // Parse pagination params
        const limit = parseInt(searchParams.get('limit') || String(DEFAULT_LIMIT));
        const offset = parseInt(searchParams.get('offset') || '0');
        const listingType = searchParams.get('type'); // 'sale', 'rent', or null for all

        // Validar slug
        if (!isValidDepartamentoSlug(slug)) {
            return NextResponse.json(
                { error: 'Departamento no válido' },
                { status: 404 }
            );
        }

        const departamento = slugToDepartamento(slug);

        // Call the new lean, paginated RPC function
        const url = `${process.env.SUPABASE_URL}/rest/v1/rpc/get_listings_for_cards`;

        console.time(`[PERF] /api/department/${slug} - Supabase RPC call`);
        const res = await fetch(url, {
            method: 'POST',
            headers: {
                'apikey': process.env.SUPABASE_SERVICE_KEY!,
                'Authorization': `Bearer ${process.env.SUPABASE_SERVICE_KEY!}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                p_departamento: departamento,
                p_listing_type: listingType || null,
                p_limit: limit,
                p_offset: offset
            }),
            next: { revalidate: 60 } // Cache for 1 minute
        });
        console.timeEnd(`[PERF] /api/department/${slug} - Supabase RPC call`);

        if (!res.ok) {
            const errorText = await res.text();
            console.error('Supabase RPC error:', errorText);
            throw new Error(`Supabase error: ${res.status}`);
        }

        const data: CardListing[] = await res.json();

        // total_count is the same for all rows
        const total = data.length > 0 ? data[0].total_count : 0;
        const hasMore = offset + data.length < total;

        return NextResponse.json({
            departamento,
            slug,
            listings: data,
            pagination: {
                total,
                limit,
                offset,
                hasMore
            }
        });
    } catch (error) {
        console.error('Error fetching department listings:', error);
        return NextResponse.json(
            { error: 'Failed to fetch department listings' },
            { status: 500 }
        );
    }
}
