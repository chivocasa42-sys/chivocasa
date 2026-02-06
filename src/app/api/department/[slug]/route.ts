import { NextResponse } from 'next/server';
import { slugToDepartamento, isValidDepartamentoSlug } from '@/lib/slugify';

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
    total_count: number;
}

export interface Municipality {
    municipio_id: number;
    municipio_name: string;
    listing_count: number;
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
        const sortBy = searchParams.get('sort') || 'recent';
        const municipio = searchParams.get('municipio'); // NEW: filter by municipality

        // Validar slug
        if (!isValidDepartamentoSlug(slug)) {
            return NextResponse.json(
                { error: 'Departamento no válido' },
                { status: 404 }
            );
        }

        const departamento = slugToDepartamento(slug);
        const headers = {
            'apikey': process.env.SUPABASE_SERVICE_KEY!,
            'Authorization': `Bearer ${process.env.SUPABASE_SERVICE_KEY!}`,
            'Content-Type': 'application/json'
        };

        // Fetch listings and municipalities in parallel
        console.time(`[PERF] /api/department/${slug} - Supabase RPC calls`);
        const [listingsRes, municipalitiesRes] = await Promise.all([
            // Listings with optional municipality filter
            fetch(`${process.env.SUPABASE_URL}/rest/v1/rpc/get_listings_for_cards`, {
                method: 'POST',
                headers,
                body: JSON.stringify({
                    p_departamento: departamento,
                    p_listing_type: listingType || null,
                    p_limit: limit,
                    p_offset: offset,
                    p_sort_by: sortBy,
                    p_municipio: municipio || null
                }),
                cache: 'no-store' // Disable caching to ensure filter is always applied
            }),
            // Fetch municipalities on initial load (offset 0), filtered by listing type
            (offset === 0 && !municipio)
                ? fetch(`${process.env.SUPABASE_URL}/rest/v1/rpc/get_municipalities_for_department`, {
                    method: 'POST',
                    headers,
                    body: JSON.stringify({
                        p_departamento: departamento,
                        p_listing_type: listingType || null  // Pass listing type for filtered counts
                    }),
                    next: { revalidate: 60 } // Shorter cache since counts depend on listing type
                })
                : Promise.resolve(null)
        ]);
        console.timeEnd(`[PERF] /api/department/${slug} - Supabase RPC calls`);

        if (!listingsRes.ok) {
            const errorText = await listingsRes.text();
            console.error('Supabase RPC error:', errorText);
            throw new Error(`Supabase error: ${listingsRes.status}`);
        }

        // Parse listings
        const rawText = await listingsRes.text();
        const fixedText = rawText.replace(/"external_id":(\d{15,})/g, '"external_id":"$1"');
        const data: CardListing[] = JSON.parse(fixedText);

        // Filter out likely misclassified "Casa" sales (actual rentals posted in wrong section)
        // Casa properties listed as "sale" but below $15,000 are almost certainly rentals
        const filteredData = data.filter(listing => {
            // Use explicit null check since price can be 0 (which is falsy)
            if (listing.listing_type === 'sale' && listing.price != null && listing.price < 15000) {
                const titleLower = (listing.title || '').toLowerCase();
                // Exclude Casa listings under $15k from sale views (likely misclassified rentals)
                if (titleLower.includes('casa') && !titleLower.includes('local') && !titleLower.includes('apartamento')) {
                    return false;
                }
            }
            return true;
        });

        // Parse municipalities if fetched
        let municipalities: Municipality[] = [];
        if (municipalitiesRes && municipalitiesRes.ok) {
            municipalities = await municipalitiesRes.json();
        }

        // Use original total from DB but adjust hasMore based on filtered results
        const total = data.length > 0 ? data[0].total_count : 0;
        const hasMore = offset + data.length < total;

        return NextResponse.json({
            departamento,
            slug,
            listings: filteredData,
            municipalities, // NEW: available municipalities for filtering
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
