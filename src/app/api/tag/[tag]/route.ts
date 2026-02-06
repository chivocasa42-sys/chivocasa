import { NextResponse } from 'next/server';

export const runtime = 'edge';

const DEFAULT_LIMIT = 24;

export interface CardListing {
    external_id: string | number;
    title: string;
    price: number;
    listing_type: 'sale' | 'rent';
    first_image: string | null;
    bedrooms: number | null;
    bathrooms: number | null;
    area: number | null;
    municipio: string | null;
    tags: string[] | null;  // For client-side tag filtering
    total_count: number;
}

export async function GET(
    request: Request,
    { params }: { params: Promise<{ tag: string }> }
) {
    try {
        const { tag } = await params;
        const { searchParams } = new URL(request.url);

        // Parse pagination params
        const limit = parseInt(searchParams.get('limit') || String(DEFAULT_LIMIT));
        const offset = parseInt(searchParams.get('offset') || '0');
        const listingType = searchParams.get('type'); // 'sale', 'rent', or null for all
        const sortBy = searchParams.get('sort') || 'recent'; // 'recent', 'price_asc', 'price_desc'

        // Decode and normalize the tag from URL
        const decodedTag = decodeURIComponent(tag)
            .split('-')
            .map(word => word.charAt(0).toUpperCase() + word.slice(1))
            .join(' ');

        // Call the RPC function to get listings by tag
        const url = `${process.env.SUPABASE_URL}/rest/v1/rpc/get_listings_by_tag`;

        console.time(`[PERF] /api/tag/${tag} - Supabase RPC call`);
        const res = await fetch(url, {
            method: 'POST',
            headers: {
                'apikey': process.env.SUPABASE_SERVICE_KEY!,
                'Authorization': `Bearer ${process.env.SUPABASE_SERVICE_KEY!}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                p_tag: decodedTag,
                p_listing_type: listingType || null,
                p_limit: limit,
                p_offset: offset,
                p_sort_by: sortBy
            }),
            next: { revalidate: 60 } // Cache for 1 minute
        });
        console.timeEnd(`[PERF] /api/tag/${tag} - Supabase RPC call`);

        if (!res.ok) {
            const errorText = await res.text();
            console.error('Supabase RPC error:', errorText);
            throw new Error(`Supabase error: ${res.status}`);
        }

        // Get raw text and convert large numbers to strings to prevent precision loss
        const rawText = await res.text();
        const fixedText = rawText.replace(/"external_id":(\d{15,})/g, '"external_id":"$1"');
        const data: CardListing[] = JSON.parse(fixedText);

        // Filter out likely misclassified "Casa" sales (actual rentals posted in wrong section)
        // When viewing Casa tag, exclude sales under $15,000 (almost certainly rentals)
        const filteredData = data.filter(listing => {
            // Use explicit null check since price can be 0 (which is falsy)
            if (decodedTag.toLowerCase() === 'casa' &&
                listing.listing_type === 'sale' &&
                listing.price != null &&
                listing.price < 15000) {
                return false;
            }
            return true;
        });

        // total_count is the same for all rows (use original DB count)
        const total = data.length > 0 ? data[0].total_count : 0;
        const hasMore = offset + data.length < total;

        return NextResponse.json({
            tag: decodedTag,
            slug: tag,
            listings: filteredData,
            pagination: {
                total,
                limit,
                offset,
                hasMore
            }
        });
    } catch (error) {
        console.error('Error fetching tag listings:', error);
        return NextResponse.json(
            { error: 'Failed to fetch tag listings' },
            { status: 500 }
        );
    }
}
