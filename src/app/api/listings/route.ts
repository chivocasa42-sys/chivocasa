import { NextResponse } from 'next/server';



export async function GET() {
    try {
        const url = `${process.env.SUPABASE_URL}/rest/v1/scrappeddata_ingest?select=*&order=last_updated.desc`;

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

        // Get raw text and convert large numbers to strings to prevent precision loss
        const rawText = await res.text();
        // Convert external_id large numbers to strings
        const fixedText = rawText.replace(/"external_id":(\d{15,})/g, '"external_id":"$1"');
        const data = JSON.parse(fixedText);
        return NextResponse.json(data);
    } catch (error) {
        console.error('Error fetching listings:', error);
        return NextResponse.json({ error: 'Failed to fetch listings' }, { status: 500 });
    }
}
