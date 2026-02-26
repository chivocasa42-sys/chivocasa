/**
 * Property Detail Layout - Dynamic Metadata & Schema.org
 *
 * Server component that generates dynamic metadata and JSON-LD for property pages.
 * Wraps the client component page.tsx to provide SEO benefits.
 */
import { Metadata } from 'next';
import { Listing } from '@/types/listing';
import {
    getShareTitle,
    getShareDescription,
    formatLocation,
    getArea,
} from '@/lib/listingFormatter';
import {
    generateListingSchema,
    generateBreadcrumbSchema,
    ListingSchemaInput,
} from '@/lib/seo';
import JsonLd from '@/components/JsonLd';

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
            next: { revalidate: 60 }, // Cache 1 minute (synchronized with API)
        });

        if (!res.ok) return null;

        // BigInt safety: replace large numbers with strings
        const rawText = await res.text();
        const fixedText = rawText.replace(/"external_id":(\d{15,})/g, '"external_id":"$1"');
        const data = JSON.parse(fixedText);

        return data && data.length > 0 ? data[0] : null;
    } catch (error) {
        console.error('Error fetching listing for metadata:', error);
        return null;
    }
}

/**
 * Generate dynamic metadata for this property
 */
export async function generateMetadata({
    params,
}: {
    params: Promise<{ id: string }>;
}): Promise<Metadata> {
    const { id } = await params;
    const listing = await getListing(id);

    if (!listing) {
        return {
            title: 'Propiedad no encontrada | SivarCasas',
            description: 'Esta propiedad no está disponible en este momento.',
        };
    }

    const title = getShareTitle(listing);
    const description = getShareDescription(listing);
    const canonicalUrl = `https://sivarcasas.com/inmuebles/${id}`;

    return {
        title: `${title} | SivarCasas`,
        description,
        openGraph: {
            title: `${title} | SivarCasas`,
            description,
            type: 'website',
            locale: 'es_SV',
            siteName: 'SivarCasas',
            url: canonicalUrl,
            images: [
                {
                    url: `/inmuebles/${id}/opengraph-image`,
                    width: 1200,
                    height: 630,
                    alt: title,
                },
            ],
        },
        twitter: {
            card: 'summary_large_image',
            title: `${title} | SivarCasas`,
            description,
            images: [`/inmuebles/${id}/opengraph-image`],
        },
        alternates: {
            canonical: canonicalUrl,
        },
    };
}

/**
 * Layout component that wraps the property page
 */
export default async function PropertyLayout({
    params,
    children,
}: {
    params: Promise<{ id: string }>;
    children: React.ReactNode;
}) {
    const { id } = await params;
    const listing = await getListing(id);

    // If no listing, just render children without schemas
    if (!listing) {
        return <>{children}</>;
    }

    // Extract location for schema
    const location = formatLocation(listing);
    const locationDepartment = typeof listing.location === 'object'
        ? listing.location?.departamento
        : undefined;

    // Prepare listing schema input
    const listingSchemaData: ListingSchemaInput = {
        id: String(listing.external_id),
        title: listing.title || 'Propiedad en SivarCasas',
        description: listing.description,
        price: listing.price,
        currency: listing.currency || 'USD',
        listingType: listing.listing_type,
        images: listing.images || undefined,
        address: location
            ? {
                municipality: location,
                department: locationDepartment,
            }
            : undefined,
        specs: {
            bedrooms: listing.specs?.bedrooms
                ? Number(listing.specs.bedrooms)
                : undefined,
            bathrooms: listing.specs?.bathrooms
                ? Number(listing.specs.bathrooms)
                : undefined,
            area_m2: getArea(listing.specs) > 0 ? getArea(listing.specs) : undefined,
        },
        datePosted: listing.published_date,
        url: `https://sivarcasas.com/inmuebles/${id}`,
    };

    const listingSchema = generateListingSchema(listingSchemaData);

    // Generate breadcrumb schema
    const breadcrumbItems = [
        { name: 'Inicio', url: 'https://sivarcasas.com' },
        { name: 'Propiedades', url: 'https://sivarcasas.com' },
        {
            name: getShareTitle(listing),
            url: `https://sivarcasas.com/inmuebles/${id}`,
        },
    ];
    const breadcrumbSchema = generateBreadcrumbSchema(breadcrumbItems);

    return (
        <>
            <JsonLd data={listingSchema} />
            <JsonLd data={breadcrumbSchema} />
            {children}
        </>
    );
}
