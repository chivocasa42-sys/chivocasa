import { NextResponse } from 'next/server';

export const runtime = 'edge';

interface TagResult {
    tag: string;
}

export async function GET(request: Request) {
    try {
        const { searchParams } = new URL(request.url);
        const query = searchParams.get('query') || '';
        const searchLower = query.toLowerCase();

        // First try the RPC function (uses scrapped_data table)
        const rpcUrl = `${process.env.SUPABASE_URL}/rest/v1/rpc/get_available_tags`;

        const rpcRes = await fetch(rpcUrl, {
            method: 'POST',
            headers: {
                'apikey': process.env.SUPABASE_SERVICE_KEY!,
                'Authorization': `Bearer ${process.env.SUPABASE_SERVICE_KEY!}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                search_query: searchLower
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

        // Extract unique tags that match the search query
        const tagSet = new Set<string>();

        data.forEach(row => {
            if (row.tags && Array.isArray(row.tags)) {
                row.tags.forEach(tag => {
                    if (tag && typeof tag === 'string' && tag.toLowerCase().includes(searchLower)) {
                        tagSet.add(tag);
                    }
                });
            }
        });

        // Convert to array, sort alphabetically, and limit to top 50
        const uniqueTags: TagResult[] = Array.from(tagSet)
            .sort((a, b) => {
                // Prioritize tags that start with the search query
                const aStarts = a.toLowerCase().startsWith(searchLower);
                const bStarts = b.toLowerCase().startsWith(searchLower);
                if (aStarts && !bStarts) return -1;
                if (!aStarts && bStarts) return 1;
                return a.localeCompare(b);
            })
            .slice(0, 50)
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
