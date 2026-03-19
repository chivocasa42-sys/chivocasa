// mobile/sw.ts
// Service Worker con Serwist — compatible con Next.js 15/16+
// Este archivo se compila a public/sw.js vía next.config.ts cuando ENABLE_PWA=true

import { defaultCache } from "@serwist/next/worker";
import { CacheFirst, NetworkFirst, StaleWhileRevalidate } from "serwist";
import { Serwist } from "serwist";

// Declarar __SW_MANIFEST sin necesitar lib "WebWorker" en tsconfig global
declare const self: Window & typeof globalThis & {
  __SW_MANIFEST: Array<{ url: string; revision: string | null }>;
};

const serwist = new Serwist({
  precacheEntries: self.__SW_MANIFEST,
  skipWaiting: true,
  clientsClaim: true,
  navigationPreload: true,
  runtimeCaching: [
    ...defaultCache,

    // Cache de imágenes de propiedades — CacheFirst (7 días)
    // Las imágenes de listados cambian poco, se prefiere velocidad
    {
      matcher: /^https:\/\/.*\.(jpg|jpeg|png|webp|gif|avif)$/i,
      handler: new CacheFirst({
        cacheName: "sivarcasas-images",
        plugins: [
          {
            cachedResponseWillBeUsed: async ({ cachedResponse }) => cachedResponse,
            requestWillFetch: async ({ request }) => request,
          },
        ],
      }),
    },

    // Cache de API — NetworkFirst (5 minutos)
    // Se prefiere datos frescos del servidor, con fallback a cache
    {
      matcher: ({ url }: { url: URL }) => url.pathname.startsWith("/api/"),
      handler: new NetworkFirst({
        cacheName: "sivarcasas-api",
        networkTimeoutSeconds: 10,
      }),
    },

    // Cache de páginas de departamentos — StaleWhileRevalidate
    // Muestra datos cacheados rápido, actualiza en segundo plano
    {
      matcher: ({ url }: { url: URL }) =>
        /^\/(ahuachapan|cabanas|chalatenango|cuscatlan|la-libertad|la-paz|la-union|morazan|san-miguel|san-salvador|san-vicente|santa-ana|sonsonate|usulutan)(\/.*)?$/.test(url.pathname),
      handler: new StaleWhileRevalidate({
        cacheName: "sivarcasas-pages",
      }),
    },
  ],
});

serwist.addEventListeners();
