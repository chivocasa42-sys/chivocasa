import type { Metadata } from 'next';
import { unstable_cache } from 'next/cache';
import TendenciasClient from '@/components/TendenciasClient';

export const metadata: Metadata = {
    title: 'Tendencias del Mercado Inmobiliario en El Salvador',
    description:
        'Analiza las tendencias del mercado inmobiliario en El Salvador. Rankings por departamento, precios promedio de venta y renta, y evolución mensual del mercado.',
    keywords: [
        'tendencias inmobiliarias',
        'mercado inmobiliario El Salvador',
        'precios casas El Salvador',
        'ranking departamentos',
        'venta casas',
        'renta apartamentos',
    ],
    alternates: {
        canonical: 'https://sivarcasas.com/tendencias',
    },
    openGraph: {
        title: 'Tendencias del Mercado Inmobiliario | sivarcasas',
        description:
            'Rankings, precios promedio y evolución mensual del mercado inmobiliario en El Salvador.',
        url: 'https://sivarcasas.com/tendencias',
        type: 'website',
    },
    twitter: {
        card: 'summary_large_image',
        title: 'Tendencias del Mercado Inmobiliario | sivarcasas',
        description:
            'Rankings, precios promedio y evolución mensual del mercado inmobiliario en El Salvador.',
    },
    robots: {
        index: true,
        follow: true,
    },
};

interface DepartmentStatsRow {
    departamento: string;
    listing_type: string;
    min_price: number;
    max_price: number;
    avg_price: number;
    count: number;
}

async function _fetchDepartmentStats() {
    try {
        const url = `${process.env.SUPABASE_URL}/rest/v1/mv_sd_depto_stats?select=*&order=count.desc`;
        const res = await fetch(url, {
            headers: {
                apikey: process.env.SUPABASE_SERVICE_KEY!,
                Authorization: `Bearer ${process.env.SUPABASE_SERVICE_KEY!}`,
            },
            next: { revalidate: 300 },
        });

        if (!res.ok) return [];

        const data: DepartmentStatsRow[] = await res.json();

        const grouped: Record<
            string,
            {
                departamento: string;
                sale: { count: number; min: number; max: number; avg: number } | null;
                rent: { count: number; min: number; max: number; avg: number } | null;
                total_count: number;
            }
        > = {};

        data.forEach((row) => {
            if (!grouped[row.departamento]) {
                grouped[row.departamento] = {
                    departamento: row.departamento,
                    sale: null,
                    rent: null,
                    total_count: 0,
                };
            }
            const stats = {
                count: row.count,
                min: row.min_price,
                max: row.max_price,
                avg: row.avg_price,
            };
            if (row.listing_type === 'sale') {
                grouped[row.departamento].sale = stats;
            } else if (row.listing_type === 'rent') {
                grouped[row.departamento].rent = stats;
            }
            grouped[row.departamento].total_count += row.count;
        });

        return Object.values(grouped).sort((a, b) => b.total_count - a.total_count);
    } catch {
        return [];
    }
}

const fetchDepartmentStats = unstable_cache(
    _fetchDepartmentStats,
    ['tendencias-dept-stats'],
    { revalidate: 300, tags: ['dept-stats'] }
);

export default async function TendenciasPage() {
    const initialData = await fetchDepartmentStats();

    return <TendenciasClient initialData={initialData} />;
}
