import { NextRequest, NextResponse } from 'next/server';

interface ColoniaResult {
    id: number;
    name: string;
    latitude: number;
    longitude: number;
    municipio: string | null;
    departamento: string | null;
}

export async function GET(request: NextRequest) {
    const { searchParams } = new URL(request.url);
    const q = searchParams.get('q');

    if (!q || q.trim().length < 2) {
        return NextResponse.json([]);
    }

    try {
        // Query sv_loc_group2 for matching colonias with coordinates
        // Join to L3 (municipio) and L5 (departamento) for context
        const res = await fetch(
            `${process.env.SUPABASE_URL}/rest/v1/rpc/search_colonias`,
            {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'apikey': process.env.SUPABASE_SERVICE_KEY!,
                    'Authorization': `Bearer ${process.env.SUPABASE_SERVICE_KEY!}`
                },
                body: JSON.stringify({ p_query: q.trim() }),
                next: { revalidate: 3600 } // Cache for 1 hour (colonias are semi-static)
            }
        );

        if (!res.ok) {
            console.error('Colonias search error:', await res.text());
            return NextResponse.json([]);
        }

        const data: ColoniaResult[] = await res.json();
        return NextResponse.json(data);
    } catch (error) {
        console.error('Colonias search error:', error);
        return NextResponse.json([]);
    }
}
