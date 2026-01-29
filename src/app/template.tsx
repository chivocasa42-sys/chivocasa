/**
 * Homepage Template
 * 
 * Server component that wraps the homepage to inject JSON-LD structured data.
 * This runs on the server, ensuring crawlers see the structured data in HTML.
 */
import { JsonLd } from '@/components/JsonLd';
import { generateOrganizationSchema, generateWebSiteSchema } from '@/lib/seo';

export default function HomeTemplate({
    children,
}: {
    children: React.ReactNode;
}) {
    // Generate structured data schemas
    const organizationSchema = generateOrganizationSchema();
    const webSiteSchema = generateWebSiteSchema();

    return (
        <>
            {/* JSON-LD Structured Data - Server Rendered */}
            <JsonLd data={organizationSchema} />
            <JsonLd data={webSiteSchema} />

            {children}
        </>
    );
}
