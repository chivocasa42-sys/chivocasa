'use client';

import { useEffect } from 'react';

/**
 * Registers the service worker on the client side.
 * Renders nothing — zero UI footprint.
 */
export default function ServiceWorkerRegistrar() {
  useEffect(() => {
    if (
      typeof window !== 'undefined' &&
      'serviceWorker' in navigator &&
      process.env.NODE_ENV === 'production'
    ) {
      window.addEventListener('load', () => {
        navigator.serviceWorker
          .register('/sw.js')
          .catch((err) => console.warn('SW registration failed:', err));
      });
    }
  }, []);

  return null;
}
