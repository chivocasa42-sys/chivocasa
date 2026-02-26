/**
 * Dynamic Open Graph Image Generator for Property Listings
 *
 * Generates 1200×630px PNG images for social sharing (WhatsApp, Facebook, Twitter/X, LinkedIn).
 * Reproduces the approved mockup design with blue gradient, official logo, and property data.
 */
import { ImageResponse } from 'next/og';
import { Listing } from '@/types/listing';
import { formatPrice, formatLocation, formatSpecsForDisplay } from '@/lib/listingFormatter';
import { LOGO_BASE64 } from '@/lib/logo-constant';

export const runtime = 'edge';
export const alt = 'Propiedad en SivarCasas';
export const size = { width: 1200, height: 630 };
export const contentType = 'image/png';

/**
 * Fetch listing data from Supabase
 */
async function getListing(id: string): Promise<Listing | null> {
    const url = `${process.env.SUPABASE_URL}/rest/v1/scrappeddata_ingest?external_id=eq.${id}&select=*`;

    try {
        const res = await fetch(url, {
            headers: {
                'apikey': process.env.SUPABASE_SERVICE_KEY!,
                'Authorization': `Bearer ${process.env.SUPABASE_SERVICE_KEY!}`,
            },
            next: { revalidate: 3600 }, // Cache 1 hour
        });

        if (!res.ok) return null;

        // BigInt safety: replace large numbers with strings
        const rawText = await res.text();
        const fixedText = rawText.replace(/"external_id":(\d{15,})/g, '"external_id":"$1"');
        const data = JSON.parse(fixedText);

        return data && data.length > 0 ? data[0] : null;
    } catch (error) {
        console.error('Error fetching listing for OG image:', {
            id,
            error: error instanceof Error ? error.message : String(error),
            url,
        });
        return null;
    }
}

export default async function Image({ params }: { params: Promise<{ id: string }> }) {
    const { id } = await params;

    console.log('[OG Image] Generating for listing ID:', id);

    const listing = await getListing(id);
    const logoData = LOGO_BASE64;

    console.log('[OG Image] Listing found:', !!listing);

    // Fallback if listing not found
    if (!listing) {
        console.warn('[OG Image] No listing found for ID:', id);
        return new ImageResponse(
            (
                <div
                    style={{
                        height: '100%',
                        width: '100%',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        background: 'linear-gradient(135deg, #1e40af 0%, #3b82f6 50%, #60a5fa 100%)',
                        color: '#ffffff',
                        fontSize: 48,
                        fontWeight: 700,
                    }}
                >
                    Propiedad no disponible
                </div>
            ),
            { ...size }
        );
    }

    // Extract data
    const price = formatPrice(listing.price, listing.listing_type);
    const type = listing.listing_type === 'sale' ? 'EN VENTA' : 'EN RENTA';
    const location = formatLocation(listing);
    const specs = formatSpecsForDisplay(listing.specs);

    try {
        return new ImageResponse(
        (
            <div
                style={{
                    height: '100%',
                    width: '100%',
                    display: 'flex',
                    background: 'linear-gradient(135deg, #1e40af 0%, #3b82f6 50%, #60a5fa 100%)',
                    padding: '50px',
                    fontFamily: 'system-ui, sans-serif',
                }}
            >
                {/* Left Column - Dominant */}
                <div
                    style={{
                        flex: 1,
                        display: 'flex',
                        flexDirection: 'column',
                        justifyContent: 'space-between',
                        paddingRight: '40px',
                    }}
                >
                    {/* Top Section - Price */}
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                        {/* Price - Large and Bold */}
                        <div
                            style={{
                                fontSize: 96,
                                fontWeight: 900,
                                color: '#ffffff',
                                lineHeight: 1,
                                marginBottom: '20px',
                            }}
                        >
                            {price}
                        </div>

                        {/* Badge - Sale/Rent */}
                        <div
                            style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                backgroundColor: '#ffffff',
                                color: '#1e40af',
                                fontSize: 18,
                                fontWeight: 700,
                                padding: '12px 24px',
                                borderRadius: '8px',
                                marginBottom: '30px',
                                alignSelf: 'flex-start',
                            }}
                        >
                            {type}
                        </div>
                    </div>

                    {/* Bottom Section - CTA */}
                    <div
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            backgroundColor: 'rgba(59, 130, 246, 0.9)',
                            border: '3px solid #ffffff',
                            borderRadius: '12px',
                            padding: '16px 32px',
                            fontSize: 22,
                            fontWeight: 700,
                            color: '#ffffff',
                            alignSelf: 'flex-start',
                        }}
                    >
                        Ver propiedad
                    </div>                </div>

                {/* Right Column - 400px */}
                <div
                    style={{
                        width: '400px',
                        display: 'flex',
                        flexDirection: 'column',
                        justifyContent: 'space-between',
                    }}
                >
                    {/* Top Section - Location & Specs */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                        {/* Location */}
                        {location && (
                            <div
                                style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '8px',
                                    backgroundColor: 'rgba(255, 255, 255, 0.2)',
                                    padding: '12px 20px',
                                    borderRadius: '8px',
                                    color: '#ffffff',
                                    fontSize: 20,
                                    fontWeight: 600,
                                }}
                            >
                                📍 {location}
                            </div>
                        )}

                        {/* Divider */}
                        {(specs.bedrooms || specs.bathrooms || specs.area) && (
                            <div
                                style={{
                                    height: '2px',
                                    backgroundColor: 'rgba(255, 255, 255, 0.3)',
                                }}
                            />
                        )}

                        {/* Specs */}
                        <div
                            style={{
                                display: 'flex',
                                flexDirection: 'column',
                                gap: '12px',
                                color: '#ffffff',
                                fontSize: 24,
                            }}
                        >
                            {specs.bedrooms && (
                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                    🛏️ {specs.bedrooms} hab
                                </div>
                            )}
                            {specs.bathrooms && (
                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                    🚿 {specs.bathrooms} baños
                                </div>
                            )}
                            {specs.area && (
                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                    📐 {specs.area}
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Bottom Section - Logo with Simplified Decoration */}
                    <div
                        style={{
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            justifyContent: 'flex-end',
                            position: 'relative',
                            paddingTop: '20px',
                        }}
                    >
                        {/* Simplified decorative element */}
                        <div
                            style={{
                                position: 'absolute',
                                bottom: '0',
                                left: '50%',
                                width: '300px',
                                height: '60px',
                                marginLeft: '-150px',
                                backgroundColor: 'rgba(59, 130, 246, 0.2)',
                                borderRadius: '50%',
                            }}
                        />

                        {/* Logo Image or Text Fallback */}
                        {logoData ? (
                            <img
                                src={logoData}
                                width={180}
                                height={82}
                                style={{
                                    position: 'relative',
                                    objectFit: 'contain',
                                }}
                                alt="SivarCasas Logo"
                            />
                        ) : (
                            <div
                                style={{
                                    position: 'relative',
                                    display: 'flex',
                                    fontSize: 32,
                                    fontWeight: 900,
                                    color: '#ffffff',
                                    letterSpacing: '-0.02em',
                                }}
                            >
                                SIVAR<span style={{ color: '#38bdf8' }}>CASAS</span>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        ),
        { ...size }
    );
    } catch (error) {
        console.error('Error generating OG image:', {
            id,
            error: error instanceof Error ? error.message : String(error),
        });

        // Return simple fallback image on error
        return new ImageResponse(
            (
                <div
                    style={{
                        height: '100%',
                        width: '100%',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        background: 'linear-gradient(135deg, #1e40af 0%, #3b82f6 50%, #60a5fa 100%)',
                        color: '#ffffff',
                        fontSize: 48,
                        fontWeight: 700,
                    }}
                >
                    SivarCasas
                </div>
            ),
            { ...size }
        );
    }
}
