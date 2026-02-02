import { NextResponse } from 'next/server';

export const runtime = 'edge';

interface TagResult {
    tag: string;
}

export async function GET() {
    try {
        // Fetch all available tags via RPC (no filtering - done client-side)
        const rpcUrl = `${process.env.SUPABASE_URL}/rest/v1/rpc/get_available_tags`;

        const rpcRes = await fetch(rpcUrl, {
            method: 'POST',
            headers: {
                'apikey': process.env.SUPABASE_SERVICE_KEY!,
                'Authorization': `Bearer ${process.env.SUPABASE_SERVICE_KEY!}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                search_query: '' // Empty to get all tags
            }),
            next: { revalidate: 300 }
        });

        if (rpcRes.ok) {
            const rpcData: { tag: string }[] = await rpcRes.json();
            if (rpcData && rpcData.length > 0) {
                return NextResponse.json({
                    tags: rpcData.map(row => ({ tag: row.tag })),
                    count: rpcData.length
                });
            }
        }

        // Fallback: query scrappeddata_ingest directly if RPC returns empty or fails
        const url = `${process.env.SUPABASE_URL}/rest/v1/scrappeddata_ingest?select=tags&limit=1000`;

        const res = await fetch(url, {
            headers: {
                'apikey': process.env.SUPABASE_SERVICE_KEY!,
                'Authorization': `Bearer ${process.env.SUPABASE_SERVICE_KEY!}`,
            },
            next: { revalidate: 300 }
        });

        if (!res.ok) {
            const errorText = await res.text();
            console.error('Supabase error:', errorText);
            throw new Error(`Supabase error: ${res.status}`);
        }

        const data: { tags: string[] | null }[] = await res.json();

        // Extract all unique tags (no search filtering - done client-side)
        const tagSet = new Set<string>();

        data.forEach(row => {
            if (row.tags && Array.isArray(row.tags)) {
                row.tags.forEach(tag => {
                    if (tag && typeof tag === 'string') {
                        tagSet.add(tag);
                    }
                });
            }
        });

        // Convert to array and sort alphabetically
        const uniqueTags: TagResult[] = Array.from(tagSet)
            .sort((a, b) => a.localeCompare(b))
            .map(tag => ({ tag }));

        return NextResponse.json({
            tags: uniqueTags,
            count: uniqueTags.length
        });
    } catch (error) {
        console.error('Error fetching tags:', error);
        return NextResponse.json(
            { error: 'Failed to fetch tags', tags: [] },
            { status: 500 }
        );
    }
}
