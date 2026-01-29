/**
 * Department Page Layout
 * 
 * Server component that provides dynamic metadata for department pages.
 * Uses generateMetadata for SSR metadata generation.
 */
import type { Metadata } from 'next';
import { JsonLd } from '@/components/JsonLd';
import { generateBreadcrumbSchema } from '@/lib/seo';
import { slugToDepartamento } from '@/lib/slugify';

interface Props {
    params: Promise<{ departamento: string; filter?: string[] }>;
    children: React.ReactNode;
}

export async function generateMetadata({ params }: { params: Promise<{ departamento: string; filter?: string[] }> }): Promise<Metadata> {
    const resolvedParams = await params;
    const departamento = slugToDepartamento(resolvedParams.departamento);
    const filter = resolvedParams.filter?.[0];

    let title = `Propiedades en ${departamento}`;
    let description = `Encuentra casas y apartamentos en ${departamento}, El Salvador. Compará precios y opciones de venta y alquiler.`;

    if (filter === 'venta') {
        title = `Casas en venta en ${departamento}`;
        description = `Propiedades en venta en ${departamento}, El Salvador. Encuentra tu próximo hogar al mejor precio.`;
    } else if (filter === 'alquiler') {
        title = `Alquiler en ${departamento}`;
        description = `Apartamentos y casas en alquiler en ${departamento}, El Salvador. Opciones para todos los presupuestos.`;
    }

    const canonical = filter
        ? `https://chivocasa.com/${resolvedParams.departamento}/${filter}`
        : `https://chivocasa.com/${resolvedParams.departamento}`;

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

export default async function DepartmentLayout({ params, children }: Props) {
    const resolvedParams = await params;
    const departamento = slugToDepartamento(resolvedParams.departamento);
    const filter = resolvedParams.filter?.[0];

    // Build breadcrumb items
    const breadcrumbItems = [
        { name: 'Inicio', url: 'https://chivocasa.com' },
        { name: departamento, url: `https://chivocasa.com/${resolvedParams.departamento}` },
    ];

    if (filter) {
        const filterName = filter === 'venta' ? 'En Venta' : 'En Alquiler';
        breadcrumbItems.push({
            name: filterName,
            url: `https://chivocasa.com/${resolvedParams.departamento}/${filter}`,
        });
    }

    const breadcrumbSchema = generateBreadcrumbSchema(breadcrumbItems);

    // Department page schema
    const departmentSchema = {
        '@context': 'https://schema.org',
        '@type': 'CollectionPage',
        name: `Propiedades en ${departamento}`,
        description: `Encuentra propiedades inmobiliarias en ${departamento}, El Salvador.`,
        url: `https://chivocasa.com/${resolvedParams.departamento}`,
        about: {
            '@type': 'Place',
            name: departamento,
            address: {
                '@type': 'PostalAddress',
                addressRegion: departamento,
                addressCountry: 'SV',
            },
        },
    };

    return (
        <>
            <JsonLd data={breadcrumbSchema} />
            <JsonLd data={departmentSchema} />
            {children}
        </>
    );
}
