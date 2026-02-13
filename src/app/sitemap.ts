import type { MetadataRoute } from 'next';

const BASE_URL = 'https://sivarcasas.com';

const departments = [
    'ahuachapan',
    'cabanas',
    'chalatenango',
    'cuscatlan',
    'la-libertad',
    'la-paz',
    'la-union',
    'morazan',
    'san-miguel',
    'san-salvador',
    'san-vicente',
    'santa-ana',
    'sonsonate',
    'usulutan',
];

export default function sitemap(): MetadataRoute.Sitemap {
    const now = new Date();

    // Static pages
    const staticPages: MetadataRoute.Sitemap = [
        {
            url: BASE_URL,
            lastModified: now,
            changeFrequency: 'daily',
            priority: 1.0,
        },
        {
            url: `${BASE_URL}/tendencias`,
            lastModified: now,
            changeFrequency: 'daily',
            priority: 0.9,
        },
        {
            url: `${BASE_URL}/valuador-de-inmuebles`,
            lastModified: now,
            changeFrequency: 'weekly',
            priority: 0.7,
        },
    ];

    // Department pages (all + venta + alquiler variants)
    const departmentPages: MetadataRoute.Sitemap = departments.flatMap((dept) => [
        {
            url: `${BASE_URL}/${dept}`,
            lastModified: now,
            changeFrequency: 'daily' as const,
            priority: 0.8,
        },
        {
            url: `${BASE_URL}/${dept}/venta`,
            lastModified: now,
            changeFrequency: 'daily' as const,
            priority: 0.7,
        },
        {
            url: `${BASE_URL}/${dept}/alquiler`,
            lastModified: now,
            changeFrequency: 'daily' as const,
            priority: 0.7,
        },
    ]);

    return [...staticPages, ...departmentPages];
}
