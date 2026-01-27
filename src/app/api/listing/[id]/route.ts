import { NextRequest, NextResponse } from 'next/server';

export const runtime = 'edge';

export async function GET(
    request: NextRequest,
    { params }: { params: Promise<{ id: string }> }
) {
    try {
        const { id } = await params;
        const url = `${process.env.SUPABASE_URL}/rest/v1/scrappeddata_ingest?external_id=eq.${id}&select=*`;

        const res = await fetch(url, {
            headers: {
                'apikey': process.env.SUPABASE_SERVICE_KEY!,
                'Authorization': `Bearer ${process.env.SUPABASE_SERVICE_KEY!}`
            },
            next: { revalidate: 60 } // Cache for 1 minute
        });

        if (!res.ok) {
            throw new Error(`Supabase error: ${res.status}`);
        }

        // Get raw text and convert large numbers to strings to prevent precision loss
        const rawText = await res.text();
        // Convert external_id large numbers to strings
        const fixedText = rawText.replace(/"external_id":(\d{15,})/g, '"external_id":"$1"');
        const data = JSON.parse(fixedText);

        if (!data || data.length === 0) {
            return NextResponse.json({ error: 'Listing not found' }, { status: 404 });
        }

        return NextResponse.json(data[0]);
    } catch (error) {
        console.error('Error fetching listing:', error);
        return NextResponse.json({ error: 'Failed to fetch listing' }, { status: 500 });
    }
}
