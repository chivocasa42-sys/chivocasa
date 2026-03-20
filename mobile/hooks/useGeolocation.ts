// mobile/hooks/useGeolocation.ts
// Geolocalización con fallback automático:
//   Plataforma nativa → @capacitor/geolocation (más preciso, sin popup del browser)
//   Browser móvil    → Web Geolocation API
//   Sin soporte      → null

export interface GeoPosition {
  lat: number;
  lng: number;
  accuracy?: number;
}

export async function getCurrentLocation(): Promise<GeoPosition | null> {
  const isNative =
    typeof window !== 'undefined' &&
    (window as any).Capacitor?.isNativePlatform();

  if (isNative) {
    try {
      const { Geolocation } = await import('@capacitor/geolocation');
      const perms = await Geolocation.requestPermissions();
      if (perms.location !== 'granted') return null;

      const pos = await Geolocation.getCurrentPosition({
        enableHighAccuracy: true,
        timeout: 10000,
      });

      return {
        lat: pos.coords.latitude,
        lng: pos.coords.longitude,
        accuracy: pos.coords.accuracy,
      };
    } catch (err) {
      console.warn('[Sivarcasas Mobile] Error en geolocalización nativa:', err);
      return null;
    }
  }

  // Fallback: Web Geolocation API (para PWA en browser)
  return new Promise((resolve) => {
    if (typeof navigator === 'undefined' || !navigator.geolocation) {
      resolve(null);
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) =>
        resolve({
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
          accuracy: pos.coords.accuracy,
        }),
      (err) => {
        console.warn('[Sivarcasas Mobile] Error en geolocalización web:', err.message);
        resolve(null);
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  });
}
