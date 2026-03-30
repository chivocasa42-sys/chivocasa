import type { Metadata } from 'next';
import TendenciasClient from '@/components/TendenciasClient';
import { fetchDepartmentStats } from '@/lib/fetchDepartmentStats';

export const metadata: Metadata = {
    title: 'Tendencias del Mercado Inmobiliario en El Salvador',
    description:
        'Analiza las tendencias del mercado inmobiliario en El Salvador. Rankings por departamento, precios promedio de venta y renta, y evolucion mensual del mercado.',
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
            'Rankings, precios promedio y evolucion mensual del mercado inmobiliario en El Salvador.',
        url: 'https://sivarcasas.com/tendencias',
        type: 'website',
    },
    twitter: {
        card: 'summary_large_image',
        title: 'Tendencias del Mercado Inmobiliario | sivarcasas',
        description:
            'Rankings, precios promedio y evolucion mensual del mercado inmobiliario en El Salvador.',
    },
    robots: {
        index: true,
        follow: true,
    },
};

export default async function TendenciasPage() {
    const initialData = await fetchDepartmentStats();

    return <TendenciasClient initialData={initialData} />;
}
