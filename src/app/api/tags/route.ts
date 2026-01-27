import { NextResponse } from 'next/server';

export const runtime = 'edge';

export async function GET(request: Request) {
    try {
        const { searchParams } = new URL(request.url);
        const query = searchParams.get('query') || '';

        // Build the SQL query to get distinct tags
        const url = `${process.env.SUPABASE_URL}/rest/v1/rpc/get_available_tags`;

        const res = await fetch(url, {
            method: 'POST',
            headers: {
                'apikey': process.env.SUPABASE_SERVICE_KEY!,
                'Authorization': `Bearer ${process.env.SUPABASE_SERVICE_KEY!}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                search_query: query.toLowerCase()
            }),
            next: { revalidate: 300 } // Cache for 5 minutes
        });

        if (!res.ok) {
            const errorText = await res.text();
            console.error('Supabase RPC error:', errorText);
            throw new Error(`Supabase error: ${res.status}`);
        }

        const data = await res.json();

        return NextResponse.json({
            tags: data,
            count: data.length
        });
    } catch (error) {
        console.error('Error fetching tags:', error);
        return NextResponse.json(
            { error: 'Failed to fetch tags', tags: [] },
            { status: 500 }
        );
    }
}
