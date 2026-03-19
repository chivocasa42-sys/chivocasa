// mobile/hooks/usePlatform.ts
// Detecta si la app corre en plataforma nativa (iOS/Android via Capacitor) o en el browser.
// Solo importa Capacitor de forma dinámica para no aumentar el bundle web.

import { useEffect, useState } from 'react';

export type Platform = 'web' | 'ios' | 'android';

export function usePlatform(): Platform {
  const [platform, setPlatform] = useState<Platform>('web');

  useEffect(() => {
    import('@capacitor/core')
      .then(({ Capacitor }) => {
        if (Capacitor.isNativePlatform()) {
          setPlatform(Capacitor.getPlatform() as Platform);
        }
      })
      .catch(() => {
        // Capacitor no disponible (entorno web normal) → permanece 'web'
      });
  }, []);

  return platform;
}

/** Versión síncrona (para uso fuera de componentes React) */
export function getPlatformSync(): Platform {
  if (typeof window === 'undefined') return 'web';
  const cap = (window as any).Capacitor;
  if (!cap?.isNativePlatform?.()) return 'web';
  return cap.getPlatform() as Platform;
}
