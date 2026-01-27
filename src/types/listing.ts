/**
 * Unified type definitions for listing data.
 * Single source of truth for all listing-related types.
 */

/**
 * Location can be a string, an object with structured data, or null.
 * Real data from Supabase may come in any of these formats.
 */
export type ListingLocation = string | {
    municipio_detectado?: string;
    [key: string]: string | undefined;
} | null;

/**
 * Specs represent property specifications.
 * Values can be string, number, or undefined since real data may be incomplete.
 */
export type ListingSpecs = {
    bedrooms?: number;
    bathrooms?: number;
    'Área construida (m²)'?: string | number;
    [key: string]: string | number | undefined;
};

/**
 * Contact information for a listing.
 */
export interface ListingContactInfo {
    nombre?: string;
    telefono?: string;
    whatsapp?: string;
}

/**
 * Main Listing interface - the single source of truth.
 * This represents a complete listing record from Supabase.
 */
export interface Listing {
    id: number;
    external_id: number;
    url: string;
    source: string;
    title: string;
    price: number;
    currency: string;
    location: ListingLocation;
    listing_type: 'sale' | 'rent';
    description: string;
    specs: ListingSpecs;
    details: Record<string, string>;
    images: string[];
    contact_info: ListingContactInfo;
    published_date: string;
    scraped_at: string;
    last_updated: string;
}

/**
 * Partial listing data for card display.
 * Use Pick to ensure type compatibility with Listing.
 * Optional fields allow for data from different sources (API pagination, etc.)
 */
export type ListingCardData = Pick<Listing, 'external_id' | 'title' | 'price' | 'listing_type'> & {
    images?: string[] | null;
    specs?: ListingSpecs | null;
    location?: ListingLocation;
};

/**
 * Statistics for a group of listings by location.
 */
export interface LocationStats {
    count: number;
    listings: Listing[];
    avg: number;
    min: number;
    max: number;
}
