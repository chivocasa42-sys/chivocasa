export interface Listing {
    id: number;
    external_id: number;
    url: string;
    source: string;
    title: string;
    price: number;
    currency: string;
    location: string | {
        municipio_detectado?: string;
        [key: string]: string | undefined;
    } | null;
    listing_type: 'sale' | 'rent';
    description: string;
    specs: {
        bedrooms?: number;
        bathrooms?: number;
        'Área construida (m²)'?: string;
        [key: string]: string | number | undefined;
    };
    details: Record<string, string>;
    images: string[];
    contact_info: {
        nombre?: string;
        telefono?: string;
        whatsapp?: string;
    };
    published_date: string;
    scraped_at: string;
    last_updated: string;
}

export interface LocationStats {
    count: number;
    listings: Listing[];
    avg: number;
    min: number;
    max: number;
}

// Minimal type for displaying listing cards (subset of Listing)
export interface ListingCardData {
    external_id: number;
    title: string;
    price: number;
    listing_type: 'sale' | 'rent';
    images?: string[] | null;
    specs?: {
        bedrooms?: number;
        bathrooms?: number;
        'Área construida (m²)'?: string | number;
        [key: string]: string | number | undefined;
    } | null;
    location?: string | {
        municipio_detectado?: string;
        [key: string]: string | undefined;
    } | null;
}

