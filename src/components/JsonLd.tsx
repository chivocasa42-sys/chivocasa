/**
 * JsonLd Component
 * 
 * Server-side component for injecting JSON-LD structured data.
 * Safe for SSR - renders in initial HTML for crawlers.
 */

interface JsonLdProps {
    data: Record<string, unknown>;
}

export function JsonLd({ data }: JsonLdProps) {
    return (
        <script
            type="application/ld+json"
            dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }}
        />
    );
}

export default JsonLd;
