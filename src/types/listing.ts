/**
 * Unified type definitions for listing data.
 * Single source of truth for all listing-related types.
 */

// Define reusable types for property specs and location
export type ListingSpecs = Record<string, string | number | undefined>;

export type ListingLocation = string | {
    municipio_detectado?: string;
    city?: string;
    state?: string;
    country?: string;
    [key: string]: string | undefined;
} | null;

export interface ListingContactInfo {
    nombre?: string;
    telefono?: string;
    whatsapp?: string;
}

/**
 * Main Listing interface - the single source of truth.
 * Accurately represents real-world data from Supabase/API.
 * Optional fields allow for partial/lean data objects.
 */
export interface Listing {
    // Core fields required for cards
    external_id: string | number; // Can be string to prevent precision loss for large IDs
    title: string;
    price: number;
    listing_type: 'sale' | 'rent';

    // Optional/Nullable fields
    id?: number; // Internal ID might not always be present in lean payloads
    url?: string;
    source?: string;
    currency?: string;
    tags?: string[] | null;

    location?: ListingLocation;

    description?: string;

    specs?: ListingSpecs | null;

    details?: Record<string, string>;

    images?: string[] | null;

    contact_info?: ListingContactInfo;

    published_date?: string;
    scraped_at?: string;
    last_updated?: string;
}

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
