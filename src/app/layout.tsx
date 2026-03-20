import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import { Analytics } from "@vercel/analytics/react";
import { SpeedInsights } from "@vercel/speed-insights/next";
import Providers from "./Providers";
import ServiceWorkerRegistrar from "@/components/ServiceWorkerRegistrar";
import PWAInstallPrompt from "@/components/PWAInstallPrompt";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
});

export const viewport: Viewport = {
  themeColor: '#10b981',
};

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
  appleWebApp: {
    capable: true,
    statusBarStyle: 'black-translucent',
    title: 'sivarcasas',
  },
  icons: {
    icon: [
      { url: '/icons/favicon-32x32.png', sizes: '32x32', type: 'image/png' },
      { url: '/icons/favicon-16x16.png', sizes: '16x16', type: 'image/png' },
    ],
    apple: [
      { url: '/icons/apple-touch-icon.png', sizes: '180x180', type: 'image/png' },
    ],
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
    <html lang="es" suppressHydrationWarning>
      {/* ── PWA / Mobile (cambio aditivo — no modifica metadata existente) ── */}
      <head>
        <link rel="manifest" href="/manifest.json" />
        <link rel="apple-touch-icon" href="/icons/apple-touch-icon.png" />
        <meta name="theme-color" content="#1e3a5f" />
      </head>
      {/* ─────────────────────────────────────────────────────────────────── */}
      <body className={inter.className}>
        <Providers>
          {children}
        </Providers>

        {/* PWA */}
        <ServiceWorkerRegistrar />
        <PWAInstallPrompt />

        {/* Performance */}
        <SpeedInsights />

        {/* Analytics */}
        <Analytics />

      </body>
    </html>
  );
}
