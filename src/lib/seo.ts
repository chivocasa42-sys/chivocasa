/**
 * SEO Utility Functions
 * 
 * Server-side utilities for generating Schema.org JSON-LD structured data.
 * All functions return plain objects ready for JSON.stringify().
 */

const SITE_URL = 'https://sivarcasas.com';
const SITE_NAME = 'sivarcasas';

/**
 * Organization Schema
 */
export function generateOrganizationSchema() {
    return {
        '@context': 'https://schema.org',
        '@type': 'RealEstateAgent',
        name: SITE_NAME,
        url: SITE_URL,
        logo: `${SITE_URL}/logo.png`,
        description: 'Plataforma de búsqueda de propiedades inmobiliarias en El Salvador',
        address: {
            '@type': 'PostalAddress',
            addressCountry: 'SV',
            addressLocality: 'San Salvador',
        },
        areaServed: {
            '@type': 'Country',
            name: 'El Salvador',
        },
        sameAs: [
            'https://twitter.com/sivarcasas',
            'https://facebook.com/sivarcasas',
        ],
    };
}

/**
 * WebSite Schema (for homepage)
 */
export function generateWebSiteSchema() {
    return {
        '@context': 'https://schema.org',
        '@type': 'WebSite',
        name: SITE_NAME,
        url: SITE_URL,
        description: 'Encuentra casas y apartamentos en venta y renta en El Salvador',
        potentialAction: {
            '@type': 'SearchAction',
            target: {
                '@type': 'EntryPoint',
                urlTemplate: `${SITE_URL}/search?q={search_term_string}`,
            },
            'query-input': 'required name=search_term_string',
        },
    };
}

/**
 * RealEstateListing Schema for individual properties
 */
export interface ListingSchemaInput {
    id: string;
    title: string;
    description?: string;
    price: number;
    currency?: string;
    listingType: 'sale' | 'rent';
    images?: string[];
    address?: {
        department?: string;
        municipality?: string;
        locality?: string;
    };
    specs?: {
        bedrooms?: number;
        bathrooms?: number;
        area_m2?: number;
    };
    datePosted?: string;
    url: string;
}

export function generateListingSchema(listing: ListingSchemaInput) {
    const schema: Record<string, unknown> = {
        '@context': 'https://schema.org',
        '@type': 'RealEstateListing',
        name: listing.title,
        description: listing.description || listing.title,
        url: listing.url,
        datePosted: listing.datePosted || new Date().toISOString(),
        offers: {
            '@type': 'Offer',
            price: listing.price,
            priceCurrency: listing.currency || 'USD',
            availability: 'https://schema.org/InStock',
            businessFunction: listing.listingType === 'rent'
                ? 'https://schema.org/LeaseOut'
                : 'https://schema.org/Sell',
        },
    };

    // Add images if available
    if (listing.images && listing.images.length > 0) {
        schema.image = listing.images.map(img => ({
            '@type': 'ImageObject',
            url: img,
        }));
    }

    // Add address/location if available
    if (listing.address) {
        schema.address = {
            '@type': 'PostalAddress',
            addressCountry: 'SV',
            addressRegion: listing.address.department,
            addressLocality: listing.address.municipality || listing.address.locality,
        };

        schema.geo = {
            '@type': 'Place',
            name: [listing.address.locality, listing.address.municipality, listing.address.department]
                .filter(Boolean)
                .join(', '),
        };
    }

    // Add property specifications if available
    if (listing.specs) {
        if (listing.specs.bedrooms) {
            schema.numberOfBedrooms = listing.specs.bedrooms;
        }
        if (listing.specs.bathrooms) {
            schema.numberOfBathroomsTotal = listing.specs.bathrooms;
        }
        if (listing.specs.area_m2) {
            schema.floorSize = {
                '@type': 'QuantitativeValue',
                value: listing.specs.area_m2,
                unitCode: 'MTK', // Square meters
            };
        }
    }

    return schema;
}

/**
 * ItemList Schema for listing pages (department, tag, search results)
 */
export function generateItemListSchema(
    items: ListingSchemaInput[],
    pageUrl: string,
    pageName: string
) {
    return {
        '@context': 'https://schema.org',
        '@type': 'ItemList',
        name: pageName,
        url: pageUrl,
        numberOfItems: items.length,
        itemListElement: items.slice(0, 10).map((item, index) => ({
            '@type': 'ListItem',
            position: index + 1,
            item: generateListingSchema(item),
        })),
    };
}

/**
 * BreadcrumbList Schema
 */
export interface BreadcrumbItem {
    name: string;
    url: string;
}

export function generateBreadcrumbSchema(items: BreadcrumbItem[]) {
    return {
        '@context': 'https://schema.org',
        '@type': 'BreadcrumbList',
        itemListElement: items.map((item, index) => ({
            '@type': 'ListItem',
            position: index + 1,
            name: item.name,
            item: item.url,
        })),
    };
}

/**
 * Department/Region Page Schema
 */
export function generateDepartmentPageSchema(
    departmentName: string,
    stats: {
        totalCount: number;
        medianPrice?: number;
        saleCount?: number;
        rentCount?: number;
    }
) {
    return {
        '@context': 'https://schema.org',
        '@type': 'CollectionPage',
        name: `Propiedades en ${departmentName}`,
        description: `${stats.totalCount} propiedades en ${departmentName}, El Salvador. ${stats.saleCount || 0} en venta y ${stats.rentCount || 0} en renta.`,
        url: `${SITE_URL}/${departmentName.toLowerCase().replace(/\s+/g, '-')}`,
        about: {
            '@type': 'Place',
            name: departmentName,
            address: {
                '@type': 'PostalAddress',
                addressRegion: departmentName,
                addressCountry: 'SV',
            },
        },
        mainEntity: {
            '@type': 'ItemList',
            numberOfItems: stats.totalCount,
        },
    };
}
