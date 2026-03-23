import type { NextConfig } from "next";
import path from "path";
import { withSerwist } from "@serwist/next";

const emptyPolyfill = path.resolve(
  import.meta.dirname ?? __dirname,
  'src/empty-polyfills.js'
);

// ─── PWA / Mobile ────────────────────────────────────────────────────────────
// El Service Worker solo se activa cuando ENABLE_PWA=true en .env.local.
// Si la variable no está definida, el comportamiento del webapp es idéntico al original.
// Para activar: agregar ENABLE_PWA=true en .env.local y ejecutar npm run build
const ENABLE_PWA = process.env.ENABLE_PWA === 'true';
// ─────────────────────────────────────────────────────────────────────────────

const baseConfig: NextConfig = {
  // ✅ output NO cambia — se mantiene SSR (sin static export)
  experimental: {
    optimizePackageImports: ['react-leaflet', 'leaflet', 'echarts'],
    cssChunking: 'strict',
    optimizeCss: true,
  },
  turbopack: {
    resolveAlias: {
      // Stub polyfills for Turbopack dev builds
      'next/dist/build/polyfills/polyfill-nomodule': './src/empty-polyfills.js',
    },
  },
  webpack(config, { isServer }) {
    // Stub polyfills for webpack production builds
    if (!isServer) {
      config.resolve.alias = {
        ...config.resolve.alias,
        'next/dist/build/polyfills/polyfill-nomodule': emptyPolyfill,
      };
    }
    return config;
  },
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: '**',
      },
    ],
  },
  async redirects() {
    const departments = [
      'ahuachapan', 'cabanas', 'chalatenango', 'cuscatlan',
      'la-libertad', 'la-paz', 'la-union', 'morazan',
      'san-miguel', 'san-salvador', 'san-vicente', 'santa-ana',
      'sonsonate', 'usulutan'
    ];

    return departments.flatMap(dept => [
      {
        source: `/tag/${dept}`,
        destination: `/${dept}`,
        permanent: true,
      },
      {
        source: `/tag/${dept}/:filter`,
        destination: `/${dept}/:filter`,
        permanent: true,
      }
    ]);
  },
};

// Aplicar wrapper PWA solo si ENABLE_PWA=true en .env.local
// De lo contrario, exportar el config base sin cambios
const exportedConfig = ENABLE_PWA
  ? withSerwist({
      swSrc: "mobile/sw.ts",   // Service Worker fuente (en carpeta mobile/)
      swDest: "public/sw.js",  // Destino compilado (servido por Next.js)
    })(baseConfig)
  : baseConfig;

export default exportedConfig;
