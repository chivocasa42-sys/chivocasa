import { NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
    const { searchParams } = new URL(request.url);
    const q = searchParams.get('q');

    if (!q || q.length < 2) {
        return NextResponse.json([]);
    }

    const params = new URLSearchParams({
        q: `${q}, El Salvador`,
        format: 'json',
        limit: '5',
        countrycodes: 'sv'
    });

    try {
        const response = await fetch(
            `https://nominatim.openstreetmap.org/search?${params}`,
            {
                headers: {
                    'User-Agent': 'SivarCasas/1.0 (https://sivarcasas.com)',
                    'Accept': 'application/json',
                    'Accept-Language': 'es,en;q=0.9'
                },
                next: { revalidate: 3600 } // Cache for 1 hour
            }
        );

        if (!response.ok) {
            return NextResponse.json([], { status: response.status });
        }

        const data = await response.json();
        return NextResponse.json(data);
    } catch (err) {
        console.error('Nominatim proxy error:', err);
        return NextResponse.json([], { status: 500 });
    }
}
