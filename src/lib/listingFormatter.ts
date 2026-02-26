/**
 * Listing Data Formatter - Single Source of Truth
 *
 * Centralizes all listing data formatting logic to eliminate duplication
 * across components (ListingCard, ListingModal, page.tsx, OG images, metadata).
 */

import { Listing, ListingSpecs, ListingLocation } from '@/types/listing';

/**
 * Format price with currency and /mes suffix for rentals
 * @example formatPrice(1500, 'rent') => "$1,500/mes"
 * @example formatPrice(250000, 'sale') => "$250,000"
 */
export function formatPrice(price: number, listingType?: 'sale' | 'rent'): string {
    if (!price || price === 0) return 'N/A';

    const formatted = '$' + price.toLocaleString('en-US');

    if (listingType === 'rent') {
        return formatted + '/mes';
    }

    return formatted;
}

/**
 * Extract area from specs with fallback logic
 * Priority: area_m2 (normalized) > legacy fields
 */
export function getArea(specs: ListingSpecs | null | undefined): number {
    if (!specs) return 0;

    // Priority: area_m2 (normalized by scraper)
    if (specs.area_m2) {
        const numValue = parseFloat(String(specs.area_m2));
        if (numValue > 0) return numValue;
    }

    // Fallback for legacy data
    const areaFields = [
        'Área construida (m²)',
        'area',
        'terreno',
        'Área del terreno',
        'm2',
        'metros'
    ];

    for (const field of areaFields) {
        const value = specs[field];
        if (value) {
            const numValue = parseFloat(String(value).replace(/[^\d.]/g, ''));
            if (numValue > 0) return numValue;
        }
    }

    return 0;
}

/**
 * Format area with m² suffix
 * @example formatArea(specs) => "120 m²" or null
 */
export function formatArea(specs: ListingSpecs | null | undefined): string | null {
    const area = getArea(specs);
    if (area <= 0) return null;
    return `${area.toLocaleString()} m²`;
}

/**
 * Get location tags array (max 3)
 * Priority: tags > location.municipio_detectado > location.departamento
 */
export function getLocationTags(listing: Pick<Listing, 'tags' | 'location'>): string[] {
    // Tags to exclude from display (all listings are in El Salvador, so redundant)
    const excludedTags = ['el salvador', 'no identificado'];

    // Prefer the tags array if it exists
    if (listing.tags && listing.tags.length > 0) {
        return listing.tags
            .filter(t => !excludedTags.includes(t.toLowerCase()))
            .slice(0, 3); // Max 3 location tags
    }

    // Fallback to building from location object
    const locationTags: string[] = [];
    const location = listing.location;

    if (location && typeof location === 'object') {
        if (location.municipio_detectado) locationTags.push(location.municipio_detectado);
        if (location.departamento) locationTags.push(location.departamento);
    } else if (typeof location === 'string') {
        locationTags.push(location);
    }

    return locationTags.slice(0, 3);
}

/**
 * Get primary location string for display
 * @example formatLocation(listing) => "San Salvador"
 */
export function formatLocation(listing: Pick<Listing, 'tags' | 'location'>): string | null {
    const tags = getLocationTags(listing);
    return tags.length > 0 ? tags[0] : null;
}

/**
 * Generate share title (short, max 60 chars)
 * @example "Venta - $250,000" or "Renta - $1,500/mes"
 */
export function getShareTitle(listing: Pick<Listing, 'title' | 'price' | 'listing_type'>): string {
    const type = listing.listing_type === 'sale' ? 'Venta' : 'Renta';
    const price = formatPrice(listing.price, listing.listing_type);
    return `${type} - ${price}`;
}

/**
 * Generate share description (120-180 chars optimal for OG)
 * @example "Propiedad en Venta • 3 hab • 2 baños • 150 m² • San Salvador • SivarCasas"
 */
export function getShareDescription(
    listing: Pick<Listing, 'specs' | 'location' | 'tags' | 'price' | 'listing_type'>
): string {
    const parts: string[] = [];

    // Type
    const type = listing.listing_type === 'sale' ? 'Venta' : 'Renta';
    parts.push(`Propiedad en ${type}`);

    // Specs
    const specs = listing.specs;
    if (specs) {
        if (specs.bedrooms) parts.push(`${specs.bedrooms} hab`);
        if (specs.bathrooms) parts.push(`${specs.bathrooms} baños`);

        const area = getArea(specs);
        if (area > 0) parts.push(`${area.toLocaleString()} m²`);
    }

    // Location
    const location = formatLocation(listing);
    if (location) parts.push(location);

    // Brand
    parts.push('SivarCasas');

    return parts.join(' • ');
}

/**
 * Get primary image URL with fallback
 */
export function getShareImage(listing: Pick<Listing, 'images'>): string {
    return getImageUrl(listing.images);
}

/**
 * Get image URL from array with fallback
 */
export function getImageUrl(images: string[] | null | undefined): string {
    if (!images || images.length === 0) {
        return '/placeholder.webp';
    }
    const firstImage = Array.isArray(images) ? images[0] : images;
    return firstImage || '/placeholder.webp';
}

/**
 * Format specs for OG image display
 * Returns object with bedrooms, bathrooms, area strings (null if not available)
 */
export function formatSpecsForDisplay(specs: ListingSpecs | null | undefined): {
    bedrooms: string | null;
    bathrooms: string | null;
    area: string | null;
} {
    if (!specs) {
        return { bedrooms: null, bathrooms: null, area: null };
    }

    return {
        bedrooms: specs.bedrooms ? String(specs.bedrooms) : null,
        bathrooms: specs.bathrooms ? String(specs.bathrooms) : null,
        area: formatArea(specs),
    };
}
