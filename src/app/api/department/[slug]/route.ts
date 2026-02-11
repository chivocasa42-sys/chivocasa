import { NextResponse } from 'next/server';
import { slugToDepartamento, isValidDepartamentoSlug } from '@/lib/slugify';

const DEFAULT_LIMIT = 24;

// Known property-type tags to extract from scraped_data tags
const PROPERTY_TYPES = new Set([
    'Casa', 'Apartamento', 'Terreno', 'Local',
    'Oficina', 'Bodega', 'Proyecto', 'Edificio', 'Finca', 'Lote'
]);

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
    published_date: string | null;
    last_updated: string | null;
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
        const priceMinRaw = searchParams.get('price_min');
        const priceMaxRaw = searchParams.get('price_max');
        const priceMin = priceMinRaw ? parseFloat(priceMinRaw) : null;
        const priceMax = priceMaxRaw ? parseFloat(priceMaxRaw) : null;

        // Multi-select filters (comma-separated)
        const municipiosRaw = searchParams.get('municipios');
        const municipios = municipiosRaw ? municipiosRaw.split(',').map(m => m.trim()).filter(Boolean) : [];
        const categoriesRaw = searchParams.get('categories');
        const categories = categoriesRaw ? categoriesRaw.split(',').map(c => c.trim()).filter(Boolean) : [];

        const hasPostFilters = municipios.length > 0 || categories.length > 0;

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

        // When post-filters are active, fetch ALL listings from SQL (no municipio filter, large limit)
        // then filter + paginate in this route. Otherwise, use SQL-level pagination for efficiency.
        const sqlLimit = hasPostFilters ? 5000 : limit;
        const sqlOffset = hasPostFilters ? 0 : offset;

        // Fetch listings, municipalities, and available categories in parallel
        console.time(`[PERF] /api/department/${slug} - Supabase RPC calls`);
        const [listingsRes, municipalitiesRes, categoriesRes] = await Promise.all([
            // Listings — no municipio filter when post-filters are active
            fetch(`${process.env.SUPABASE_URL}/rest/v1/rpc/get_listings_for_cards`, {
                method: 'POST',
                headers,
                body: JSON.stringify({
                    p_departamento: departamento,
                    p_listing_type: listingType || null,
                    p_limit: sqlLimit,
                    p_offset: sqlOffset,
                    p_sort_by: sortBy,
                    p_municipio: null // Always null — we filter post-SQL for multi-select
                }),
                cache: 'no-store'
            }),
            // Fetch municipalities on initial load (offset 0)
            (offset === 0)
                ? fetch(`${process.env.SUPABASE_URL}/rest/v1/rpc/get_municipalities_for_department`, {
                    method: 'POST',
                    headers,
                    body: JSON.stringify({
                        p_departamento: departamento,
                        p_listing_type: listingType || null
                    }),
                    next: { revalidate: 60 }
                })
                : Promise.resolve(null),
            // Fetch available categories (per-department property-type tags) on initial load
            (offset === 0)
                ? fetch(`${process.env.SUPABASE_URL}/rest/v1/rpc/get_categories_for_department`, {
                    method: 'POST',
                    headers,
                    body: JSON.stringify({
                        p_departamento: departamento,
                        p_listing_type: listingType || null
                    }),
                    next: { revalidate: 300 } // Cache for 5 minutes
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
        let filtered = data.filter(listing => {
            if (listing.listing_type === 'sale' && listing.price != null && listing.price < 15000) {
                const titleLower = (listing.title || '').toLowerCase();
                if (titleLower.includes('casa') && !titleLower.includes('local') && !titleLower.includes('apartamento')) {
                    return false;
                }
            }
            return true;
        });

        // Apply price range filter
        if (priceMin != null || priceMax != null) {
            filtered = filtered.filter(listing => {
                if (priceMin != null && listing.price < priceMin) return false;
                if (priceMax != null && listing.price > priceMax) return false;
                return true;
            });
        }

        // Apply municipio filter (OR within group — listing matches ANY selected municipio)
        if (municipios.length > 0) {
            filtered = filtered.filter(listing =>
                listing.municipio != null && municipios.includes(listing.municipio)
            );
        }

        // Apply category filter (OR within group — title contains ANY selected category)
        // AND logic: this runs after municipio filter, so both must match
        if (categories.length > 0) {
            filtered = filtered.filter(listing => {
                const titleLower = (listing.title || '').toLowerCase();
                return categories.some(cat => titleLower.includes(cat.toLowerCase()));
            });
        }

        // Parse municipalities if fetched
        let municipalities: Municipality[] = [];
        if (municipalitiesRes && municipalitiesRes.ok) {
            municipalities = await municipalitiesRes.json();
        }

        // Extract available categories from RPC response
        let availableCategories: string[] = [];
        if (categoriesRes && categoriesRes.ok) {
            try {
                const catData: { category: string }[] = await categoriesRes.json();
                const categorySet = new Set(catData.map(r => r.category));
                // Sort by the order defined in PROPERTY_TYPES
                availableCategories = [...PROPERTY_TYPES].filter(pt => categorySet.has(pt));
            } catch {
                console.error('Error parsing categories');
            }
        }

        // Calculate pagination based on filtered results
        const total = hasPostFilters ? filtered.length : (data.length > 0 ? data[0].total_count : 0);
        const paginatedListings = hasPostFilters
            ? filtered.slice(offset, offset + limit)
            : filtered;
        const hasMore = hasPostFilters
            ? (offset + limit) < filtered.length
            : offset + data.length < (data.length > 0 ? data[0].total_count : 0);

        return NextResponse.json({
            departamento,
            slug,
            listings: paginatedListings,
            municipalities,
            availableCategories,
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
