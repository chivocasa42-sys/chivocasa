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
  metadataBase: new URL('https://chivocasa.com'),
  title: {
    default: 'ChivoCasa - Propiedades en El Salvador',
    template: '%s | ChivoCasa',
  },
  description:
    'Encuentra casas y apartamentos en venta y renta en El Salvador. Compará precios por departamento y descubrí las mejores oportunidades del mercado inmobiliario.',
  keywords: ['inmuebles', 'propiedades', 'casas', 'apartamentos', 'El Salvador', 'venta', 'renta', 'bienes raíces'],
  authors: [{ name: 'ChivoCasa' }],
  creator: 'ChivoCasa',
  publisher: 'ChivoCasa',
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
    siteName: 'ChivoCasa',
    title: 'ChivoCasa - Propiedades en El Salvador',
    description: 'Encuentra casas y apartamentos en venta y renta en El Salvador.',
    images: [
      {
        url: '/og-image.png',
        width: 1200,
        height: 630,
        alt: 'ChivoCasa - Propiedades en El Salvador',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'ChivoCasa - Propiedades en El Salvador',
    description: 'Encuentra casas y apartamentos en venta y renta en El Salvador.',
    images: ['/og-image.png'],
    creator: '@chivocasa',
  },
  alternates: {
    canonical: 'https://chivocasa.com',
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
