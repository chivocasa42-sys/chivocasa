/**
 * Tag Page Layout
 * 
 * Server component that provides dynamic metadata for tag pages.
 * Uses generateMetadata for SSR metadata generation.
 */
import type { Metadata } from 'next';
import { JsonLd } from '@/components/JsonLd';
import { generateBreadcrumbSchema } from '@/lib/seo';

interface Props {
    params: Promise<{ tag: string; filter?: string[] }>;
    children: React.ReactNode;
}

// Format tag slug to display name
function formatTagName(slug: string): string {
    return slug
        .split('-')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
}

export async function generateMetadata({ params }: { params: Promise<{ tag: string; filter?: string[] }> }): Promise<Metadata> {
    const resolvedParams = await params;
    const tagName = formatTagName(resolvedParams.tag);
    const filter = resolvedParams.filter?.[0];

    let title = `${tagName} - Propiedades`;
    let description = `Encuentra propiedades en ${tagName}, El Salvador. Casas y apartamentos en venta y alquiler.`;

    if (filter === 'venta') {
        title = `${tagName} - Propiedades en venta`;
        description = `Casas y apartamentos en venta en ${tagName}, El Salvador.`;
    } else if (filter === 'alquiler') {
        title = `${tagName} - Propiedades en alquiler`;
        description = `Casas y apartamentos en alquiler en ${tagName}, El Salvador.`;
    }

    const canonical = filter
        ? `https://chivocasa.com/tag/${resolvedParams.tag}/${filter}`
        : `https://chivocasa.com/tag/${resolvedParams.tag}`;

    return {
        title,
        description,
        openGraph: {
            title: `${title} | ChivoCasa`,
            description,
            type: 'website',
            locale: 'es_SV',
            siteName: 'ChivoCasa',
            url: canonical,
        },
        twitter: {
            card: 'summary_large_image',
            title: `${title} | ChivoCasa`,
            description,
        },
        alternates: {
            canonical,
        },
    };
}

export default async function TagLayout({ params, children }: Props) {
    const resolvedParams = await params;
    const tagName = formatTagName(resolvedParams.tag);
    const filter = resolvedParams.filter?.[0];

    // Build breadcrumb items
    const breadcrumbItems = [
        { name: 'Inicio', url: 'https://chivocasa.com' },
        { name: tagName, url: `https://chivocasa.com/tag/${resolvedParams.tag}` },
    ];

    if (filter) {
        const filterName = filter === 'venta' ? 'En Venta' : 'En Alquiler';
        breadcrumbItems.push({
            name: filterName,
            url: `https://chivocasa.com/tag/${resolvedParams.tag}/${filter}`,
        });
    }

    const breadcrumbSchema = generateBreadcrumbSchema(breadcrumbItems);

    // Tag page schema
    const tagPageSchema = {
        '@context': 'https://schema.org',
        '@type': 'CollectionPage',
        name: `Propiedades en ${tagName}`,
        description: `Encuentra propiedades inmobiliarias en ${tagName}, El Salvador.`,
        url: `https://chivocasa.com/tag/${resolvedParams.tag}`,
        about: {
            '@type': 'Place',
            name: tagName,
            address: {
                '@type': 'PostalAddress',
                addressCountry: 'SV',
            },
        },
    };

    return (
        <>
            <JsonLd data={breadcrumbSchema} />
            <JsonLd data={tagPageSchema} />
            {children}
        </>
    );
}
