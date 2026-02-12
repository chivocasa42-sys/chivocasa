import { NextRequest, NextResponse } from 'next/server';

// --- Types ---

interface ValuationInput {
    lat: number;
    lng: number;
    area_m2: number;
    bedrooms: number | null;
    bathrooms: number | null;
    parking: number | null;
    property_type: string; // casa, apartamento, lote, local
}

interface AvmValueRow {
    listing_type: string;
    property_class: string;
    area_m2: number;
    radius_used_m: number | null;
    comps_used: number;
    est_price: number | null;
    est_low: number | null;
    est_high: number | null;
    est_price_m2: number | null;
    confidence: number;
    method: string;
    notes: string;
}

interface AvmCompRow {
    comp_rank: number;
    comp_external_id: string;
    comp_title: string;
    comp_source: string;
    comp_listing_type: string;
    comp_property_class: string;
    comp_price: number;
    comp_area_m2: number;
    comp_price_m2: number;
    distance_m: number;
    days_old: number;
    comp_active: boolean;
    comp_bedrooms: number | null;
    comp_bathrooms: number | null;
    comp_parking: number | null;
    total_weight: number;
    comp_url: string | null;
    match_mode: string;
    selected_radius_m: number | null;
}

// --- Supabase RPC helpers ---

const SB_URL = process.env.SUPABASE_URL!;
const SB_KEY = process.env.SUPABASE_SERVICE_KEY!;
const SB_HEADERS = {
    'Content-Type': 'application/json',
    'apikey': SB_KEY,
    'Authorization': `Bearer ${SB_KEY}`
};

async function callRpc<T>(fn: string, params: Record<string, unknown>): Promise<T> {
    const res = await fetch(`${SB_URL}/rest/v1/rpc/${fn}`, {
        method: 'POST',
        headers: SB_HEADERS,
        body: JSON.stringify(params),
        next: { revalidate: 300 }
    });
    if (!res.ok) {
        const errText = await res.text();
        throw new Error(`${fn} error: ${errText}`);
    }
    return res.json();
}

// --- Main handler ---

export async function POST(request: NextRequest) {
    try {
        const body: ValuationInput = await request.json();

        // Validate required fields
        if (!body.lat || !body.lng || !body.area_m2 || body.area_m2 <= 0) {
            return NextResponse.json(
                { error: 'lat, lng, and area_m2 (> 0) are required' },
                { status: 400 }
            );
        }
        if (!body.property_type) {
            return NextResponse.json(
                { error: 'property_type is required' },
                { status: 400 }
            );
        }

        const commonParams = {
            p_lat: body.lat,
            p_lon: body.lng,
            p_area_m2: body.area_m2,
            p_property_class: body.property_type,
            p_bedrooms: body.bedrooms ?? null,
            p_bathrooms: body.bathrooms ?? null,
            p_parking: body.parking ?? null,
        };

        // Run sale valuation, rent valuation, and top comps in parallel
        const [saleRows, rentRows, compRows] = await Promise.all([
            callRpc<AvmValueRow[]>('avm_value_point', {
                ...commonParams,
                p_listing_type: 'sale',
            }),
            callRpc<AvmValueRow[]>('avm_value_point', {
                ...commonParams,
                p_listing_type: 'rent',
            }),
            callRpc<AvmCompRow[]>('avm_nearest_matches', {
                ...commonParams,
                p_listing_type: 'sale',
                p_limit: 5,
            }),
        ]);

        const sale = saleRows[0];

        // Insufficient data check
        if (!sale || sale.method === 'insufficient_data' || sale.est_price == null) {
            return NextResponse.json({
                error: 'insufficient_data',
                message: 'No hay suficientes propiedades comparables en esta zona para generar una estimación.',
                sample_count: sale?.comps_used ?? 0,
                radius_used: sale?.radius_used_m ? sale.radius_used_m / 1000 : 0
            }, { status: 200 });
        }

        const estimatedValue = sale.est_price;

        // Rent estimate: use SQL result or fallback to 0.6% of value
        const rent = rentRows[0];
        let estimatedRent: number | null = null;
        let rentPercentage: number | null = null;
        let rentSampleCount = 0;

        if (rent && rent.est_price != null && rent.method !== 'insufficient_data') {
            estimatedRent = Math.round(rent.est_price);
            rentSampleCount = rent.comps_used;
            rentPercentage = estimatedValue > 0
                ? Math.round((estimatedRent / estimatedValue) * 1000) / 10
                : null;
        } else {
            estimatedRent = Math.round(estimatedValue * 0.006);
            rentPercentage = 0.6;
        }

        // 12-month projection (5% annual appreciation)
        const appreciationRate = 0.05;
        const projection12m = Math.round(estimatedValue * (1 + appreciationRate));

        // Build top comps for display
        const topComps = compRows.map(c => ({
            title: c.comp_title,
            price: c.comp_price,
            area_m2: Math.round(c.comp_area_m2),
            price_per_m2: Math.round(c.comp_price_m2),
            bedrooms: c.comp_bedrooms,
            bathrooms: c.comp_bathrooms,
            parking: c.comp_parking,
            distance_km: Math.round(c.distance_m / 10) / 100, // m → km, 2 decimals
            similarity: Math.round(c.total_weight * 100),
            url: c.comp_url,
            active: c.comp_active,
            days_old: c.days_old,
        }));

        const result = {
            estimated_value: Math.round(estimatedValue),
            range_low: Math.round(sale.est_low!),
            range_high: Math.round(sale.est_high!),
            confidence: sale.confidence,
            price_per_m2: Math.round(sale.est_price_m2!),
            estimated_rent: estimatedRent,
            rent_percentage: rentPercentage,
            projection_12m: projection12m,
            appreciation_rate: appreciationRate,
            sample_count: sale.comps_used,
            rent_sample_count: rentSampleCount,
            comps_used: sale.comps_used,
            radius_used: sale.radius_used_m ? sale.radius_used_m / 1000 : 0,
            method: sale.method,
            top_comps: topComps
        };

        return NextResponse.json(result);
    } catch (error) {
        console.error('Valuador error:', error);
        return NextResponse.json(
            { error: 'Error al calcular la estimación' },
            { status: 500 }
        );
    }
}
