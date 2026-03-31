import type { Metadata } from 'next';
import DepartmentMarketClient from '@/components/DepartmentMarketClient';
import { fetchDepartmentStats } from '@/lib/fetchDepartmentStats';

export const metadata: Metadata = {
    title: 'Precios y oferta por departamento | sivarcasas',
    description:
        'Compara precios medios, rangos de precios y oferta inmobiliaria por departamento en El Salvador.',
    alternates: {
        canonical: 'https://sivarcasas.com/departamentos',
    },
    openGraph: {
        title: 'Precios y oferta por departamento | sivarcasas',
        description:
            'Compara el mercado inmobiliario por departamento y descubre dónde conviene buscar en El Salvador.',
        url: 'https://sivarcasas.com/departamentos',
        type: 'website',
    },
    twitter: {
        card: 'summary_large_image',
        title: 'Precios y oferta por departamento | sivarcasas',
        description:
            'Compara el mercado inmobiliario por departamento y descubre dónde conviene buscar en El Salvador.',
    },
};

export default async function DepartamentosPage() {
    const initialData = await fetchDepartmentStats();

    return <DepartmentMarketClient initialData={initialData} />;
}
