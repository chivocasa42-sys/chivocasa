import type { Metadata } from 'next';

export const metadata: Metadata = {
    title: 'Valuador de Inmuebles en El Salvador | SivarCasas',
    description: 'Estimá el valor de tu propiedad basado en datos reales del mercado inmobiliario salvadoreño. Calculá precio por m², renta estimada y proyección a 12 meses.',
    keywords: ['valuador', 'inmuebles', 'El Salvador', 'precio m2', 'valor propiedad', 'estimación', 'bienes raíces'],
    openGraph: {
        title: 'Valuador de Inmuebles en El Salvador',
        description: 'Estimá el valor de tu propiedad basado en datos reales del mercado salvadoreño.',
        type: 'website',
    },
    alternates: {
        canonical: 'https://sivarcasas.com/valuador-de-inmuebles',
    },
};

export default function ValuadorLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return children;
}
