import type { NextConfig } from "next";
import path from "path";

const emptyPolyfill = path.resolve(
  import.meta.dirname ?? __dirname,
  'src/empty-polyfills.js'
);

const nextConfig: NextConfig = {
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

export default nextConfig;
