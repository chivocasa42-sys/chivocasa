import { NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
    const { searchParams } = new URL(request.url);
    const lat = searchParams.get('lat');
    const lng = searchParams.get('lng');

    if (!lat || !lng) {
        return NextResponse.json({ error: 'lat and lng required' }, { status: 400 });
    }

    try {
        const params = new URLSearchParams({
            lat,
            lon: lng,
            format: 'json',
            zoom: '18',
            addressdetails: '1'
        });

        const response = await fetch(
            `https://nominatim.openstreetmap.org/reverse?${params}`,
            {
                headers: {
                    'User-Agent': 'ChivocasaBot/1.0 (https://github.com/chivocasa42-sys)',
                    'Accept': 'application/json',
                    'Accept-Language': 'es,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate',
                    'Connection': 'keep-alive'
                },
                next: { revalidate: 86400 } // Cache for 24 hours
            }
        );

        if (!response.ok) {
            return NextResponse.json({ name: null }, { status: 200 });
        }

        const data = await response.json();
        const address = data.address || {};

        // Build a specific, meaningful name from address parts
        // Priority: residential area / neighbourhood / suburb, then city, then state
        const parts: string[] = [];
        const specificPlace = address.residential || address.neighbourhood || address.suburb || address.quarter;
        if (specificPlace) {
            parts.push(specificPlace);
        }
        if (address.city || address.town || address.village || address.municipality) {
            const city = address.city || address.town || address.village || address.municipality;
            // Avoid duplicating if specific place already equals city
            if (city !== specificPlace) {
                parts.push(city);
            }
        }
        if (address.state) {
            // Avoid duplicating if state equals city
            const lastPart = parts[parts.length - 1];
            if (address.state !== lastPart) {
                parts.push(address.state);
            }
        }

        const name = parts.length > 0 ? parts.join(', ') : (data.display_name?.split(',').slice(0, 3).join(',').trim() || null);

        return NextResponse.json({ name });
    } catch (err) {
        console.error('Reverse geocode error:', err);
        return NextResponse.json({ name: null }, { status: 200 });
    }
}
