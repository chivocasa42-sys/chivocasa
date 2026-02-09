import { NextRequest, NextResponse } from 'next/server';

/**
 * API Route: /api/nearby-listings
 * Query params: lat, lng, radius (km), sort_by, limit, offset
 * Returns:
 *   - stats: Median price stats for sale/rent nearby
 *   - listings: Paginated nearby listings
 *   - pagination: total_count, limit, offset, has_more
 */

interface PriceStats {
    listing_type: 'sale' | 'rent';
    listings_count: number;
    avg_price: string;
    median_price: string;
    min_price: string;
    max_price: string;
}

interface NearbyListing {
    external_id: string | number;
    listing_type: 'sale' | 'rent';
    price: number;
    last_updated: string;
    title: string;
    url: string;
    source: string;
    lat: number;
    lng: number;
    distance_km: string;
    total_count: number;
    // Extended fields from JSONB
    specs: {
        bedrooms?: number | null;
        bathrooms?: number | null;
        area_m2?: number | null;
    } | null;
    tags: string[] | null;
    first_image: string | null;
}

export async function GET(request: NextRequest) {
    const { searchParams } = new URL(request.url);
    const lat = searchParams.get('lat');
    const lng = searchParams.get('lng');
    const radius = searchParams.get('radius') || '2';
    const sortBy = searchParams.get('sort_by') || 'distance_asc';
    const limit = searchParams.get('limit') || '5';
    const offset = searchParams.get('offset') || '0';
    const listingType = searchParams.get('listing_type'); // Optional: 'sale' or 'rent'

    // Validate required params
    if (!lat || !lng) {
        return NextResponse.json(
            { error: 'Missing required parameters: lat, lng' },
            { status: 400 }
        );
    }

    const latNum = parseFloat(lat);
    const lngNum = parseFloat(lng);
    const radiusNum = parseFloat(radius);
    const limitNum = Math.min(Math.max(1, parseInt(limit)), 20); // 1-20 range
    const offsetNum = Math.max(0, parseInt(offset));

    // Validate numeric values
    if (isNaN(latNum) || isNaN(lngNum) || isNaN(radiusNum)) {
        return NextResponse.json(
            { error: 'Invalid numeric values for lat, lng, or radius' },
            { status: 400 }
        );
    }

    // Validate sortBy
    const validSortOptions = ['distance_asc', 'recent', 'price_asc', 'price_desc'];
    const sortByValue = validSortOptions.includes(sortBy) ? sortBy : 'distance_asc';

    // Determine listing types to query
    const validListingTypes = ['sale', 'rent'];
    const listingTypesForListings = listingType && validListingTypes.includes(listingType)
        ? [listingType]
        : ['sale', 'rent'];

    // Clamp radius to 0.5 - 10 km
    const clampedRadius = Math.max(0.5, Math.min(10, radiusNum));

    try {
        // Call both Supabase RPC functions in parallel
        const [statsRes, listingsRes] = await Promise.all([
            // fn_listing_price_stats_nearby - for stats cards
            fetch(
                `${process.env.SUPABASE_URL}/rest/v1/rpc/fn_listing_price_stats_nearby`,
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'apikey': process.env.SUPABASE_SERVICE_KEY!,
                        'Authorization': `Bearer ${process.env.SUPABASE_SERVICE_KEY!}`
                    },
                    body: JSON.stringify({
                        p_lat: latNum,
                        p_lng: lngNum,
                        p_radius_km: clampedRadius,
                        p_listing_types: ['sale', 'rent'],
                        p_active_only: true
                    }),
                    next: { revalidate: 60 }
                }
            ),
            // fn_listings_nearby_page - for paginated listings (filtered by type)
            fetch(
                `${process.env.SUPABASE_URL}/rest/v1/rpc/fn_listings_nearby_page`,
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'apikey': process.env.SUPABASE_SERVICE_KEY!,
                        'Authorization': `Bearer ${process.env.SUPABASE_SERVICE_KEY!}`
                    },
                    body: JSON.stringify({
                        p_lat: latNum,
                        p_lng: lngNum,
                        p_radius_km: clampedRadius,
                        p_listing_types: listingTypesForListings,
                        p_active_only: true,
                        p_sort_by: sortByValue,
                        p_limit: limitNum,
                        p_offset: offsetNum
                    }),
                    next: { revalidate: 60 }
                }
            )
        ]);

        if (!statsRes.ok) {
            const errorText = await statsRes.text();
            console.error('Stats API error:', errorText);
            throw new Error(`Stats function error: ${statsRes.status}`);
        }

        if (!listingsRes.ok) {
            const errorText = await listingsRes.text();
            console.error('Listings API error:', errorText);
            throw new Error(`Listings function error: ${listingsRes.status}`);
        }

        const stats: PriceStats[] = await statsRes.json();

        // Parse listings as raw text first, then fix large external_id numbers
        // to prevent JavaScript precision loss (IDs > Number.MAX_SAFE_INTEGER)
        const listingsRaw = await listingsRes.text();
        const listingsFixed = listingsRaw.replace(/"external_id":(\d{15,})/g, '"external_id":"$1"');
        const listings: NearbyListing[] = JSON.parse(listingsFixed);

        // Extract total_count from first listing (all rows have same total_count)
        const totalCount = listings.length > 0 ? listings[0].total_count : 0;

        return NextResponse.json({
            stats,
            listings,
            pagination: {
                total_count: totalCount,
                limit: limitNum,
                offset: offsetNum,
                has_more: offsetNum + listings.length < totalCount
            },
            meta: {
                lat: latNum,
                lng: lngNum,
                radius_km: clampedRadius,
                sort_by: sortByValue
            }
        });

    } catch (error) {
        console.error('Error fetching nearby listings:', error);
        return NextResponse.json(
            { error: 'Failed to fetch nearby listings' },
            { status: 500 }
        );
    }
}
