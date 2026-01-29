import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Analytics } from "@vercel/analytics/react";
import { SpeedInsights } from "@vercel/speed-insights/next";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL('https://sivarcasas.com'),
  title: {
    default: 'sivarcasas - Propiedades en El Salvador',
    template: '%s | sivarcasas',
  },
  description:
    'Encuentra casas y apartamentos en venta y renta en El Salvador. Compará precios por departamento y descubrí las mejores oportunidades del mercado inmobiliario.',
  keywords: ['inmuebles', 'propiedades', 'casas', 'apartamentos', 'El Salvador', 'venta', 'renta', 'bienes raíces'],
  authors: [{ name: 'sivarcasas' }],
  creator: 'sivarcasas',
  publisher: 'sivarcasas',
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      'max-video-preview': -1,
      'max-image-preview': 'large',
      'max-snippet': -1,
    },
  },
  openGraph: {
    type: 'website',
    locale: 'es_SV',
    siteName: 'sivarcasas',
    title: 'sivarcasas - Propiedades en El Salvador',
    description: 'Encuentra casas y apartamentos en venta y renta en El Salvador.',
    images: [
      {
        url: '/og-image.png',
        width: 1200,
        height: 630,
        alt: 'sivarcasas - Propiedades en El Salvador',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'sivarcasas - Propiedades en El Salvador',
    description: 'Encuentra casas y apartamentos en venta y renta en El Salvador.',
    images: ['/og-image.png'],
    creator: '@sivarcasas',
  },
  alternates: {
    canonical: 'https://sivarcasas.com',
  },
};

// 20260128 Cambio para usar Analitycs Vercel con ChatGPT
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es">
      <body className={inter.className}>
        {children}

        {/* Performance */}
        <SpeedInsights />

        {/* Analytics */}
        <Analytics />

      </body>
    </html>
  );
}
