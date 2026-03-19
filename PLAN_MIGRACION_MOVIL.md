# Plan de Migración: Sivarcasas Web → App Móvil (PWA + Capacitor)

> **Versión 3.0 — Con análisis de impacto y aislamiento total** | Marzo 2026
> Esta versión garantiza que **ningún archivo existente del webapp sea modificado**.
> Todo el código móvil vive en una carpeta `mobile/` separada.

---

## 🔍 Análisis de Impacto: ¿Qué rompía el plan anterior?

Antes de ejecutar cualquier cambio, se validaron todos los archivos que el plan v2.0 proponía modificar.
A continuación, el resultado del análisis:

### Archivos existentes que el plan v2.0 modificaría ❌

| Archivo Existente | Cambio Propuesto | Impacto |
|---|---|---|
| `next.config.ts` | Agregar `withSerwist(...)` como wrapper | 🔴 Rompe el webpack config actual y los polyfills |
| `next.config.ts` | Cambiar `output: 'export'` | 🔴 Rompe SSR, redirects y API routes completamente |
| `src/app/layout.tsx` | Agregar `manifest`, `themeColor`, `viewport` | 🟡 Riesgo de conflicto con metadata existente de SEO |
| `src/app/globals.css` | Agregar reglas CSS móviles (`safe-area`, `tap-highlight`) | 🟡 Puede afectar estilos actuales del webapp |
| `src/hooks/` | Agregar `usePlatform.ts`, `useMobile.ts`, etc. | 🟡 Bajo, pero mezcla código móvil con código web |
| `package.json` | Agregar dependencias de Capacitor y Serwist | 🟡 Aumenta bundle size del webapp si no se toman precauciones |

### Archivos nuevos (sin conflicto) ✅

| Archivo Nuevo | Descripción |
|---|---|
| `public/manifest.json` | Solo se crea si no existe — sin conflicto |
| `public/icons/` | Carpeta nueva de íconos PWA |
| `capacitor.config.ts` | Archivo nuevo en raíz |
| `mobile/` | **Toda la lógica móvil nueva va aquí** |

---

## 🛡️ Principio: Aislamiento Total — Zero Touch al Código Actual

**Regla fundamental de este plan:**

> ✅ **Se crearán archivos nuevos** dentro de `mobile/`
> ❌ **No se modificará ningún archivo existente** del webapp

La única excepción controlada es `next.config.ts`, que se tocará **solo** para registrar el Service Worker mediante un import condicional que no afecta el comportamiento web normal.

---

## 📁 Nueva Arquitectura de Carpetas

```
chivocasa/                          ← Raíz del proyecto (sin cambios)
├── src/                            ← ❌ NO SE TOCA — código webapp intacto
│   ├── app/                        ← ❌ NO SE TOCA
│   ├── components/                 ← ❌ NO SE TOCA
│   ├── hooks/                      ← ❌ NO SE TOCA
│   └── ...
├── public/                         ← Se agregan archivos nuevos únicamente
│   ├── manifest.json               ← [NUEVO] Config PWA
│   ├── icons/                      ← [NUEVO] Íconos PWA
│   │   ├── icon-192x192.png
│   │   ├── icon-512x512.png
│   │   └── apple-touch-icon.png
│   └── screenshots/                ← [NUEVO] Capturas para manifest
│
├── mobile/                         ← [NUEVA CARPETA] Todo lo móvil aquí
│   ├── README.md                   ← Documentación del módulo móvil
│   ├── sw.ts                       ← Service Worker (Serwist)
│   ├── capacitor.config.ts         ← Config de Capacitor
│   ├── hooks/                      ← Hooks exclusivos para móvil
│   │   ├── usePlatform.ts
│   │   ├── useGeolocation.ts
│   │   ├── useShare.ts
│   │   └── usePushNotifications.ts
│   ├── components/                 ← Componentes exclusivos para móvil
│   │   ├── MobileInstallBanner.tsx ← Banner "Instalar App"
│   │   └── MobileSafeArea.tsx      ← Wrapper de safe areas para iOS
│   └── styles/
│       └── mobile.css              ← Estilos CSS exclusivos para móvil
│
├── next.config.ts                  ← ⚠️ Cambio mínimo y reversible (ver sección)
├── package.json                    ← Se agregan dependencias nuevas
└── capacitor.config.ts             ← [NUEVO] Symlink o copia desde mobile/
```

---

## 📱 Fase 1A: Archivos PWA en `public/` (1–2 días)

> **Impacto en webapp:** ✅ Cero. Solo se agregan archivos nuevos.

### 1.1 Crear `public/manifest.json`

Este archivo es **aditivo** — los navegadores de escritorio lo ignoran si no hay bandera de instalación PWA.

```json
{
  "name": "Sivarcasas - Propiedades en El Salvador",
  "short_name": "Sivarcasas",
  "description": "Encuentra casas y apartamentos en venta y renta en El Salvador",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#ffffff",
  "theme_color": "#1e3a5f",
  "orientation": "portrait",
  "icons": [
    {
      "src": "/icons/icon-192x192.png",
      "sizes": "192x192",
      "type": "image/png",
      "purpose": "any maskable"
    },
    {
      "src": "/icons/icon-512x512.png",
      "sizes": "512x512",
      "type": "image/png",
      "purpose": "any maskable"
    }
  ]
}
```

### 1.2 Crear íconos PWA en `public/icons/`

Crear la carpeta `public/icons/` con:
- `icon-192x192.png` — Para Android Chrome
- `icon-512x512.png` — Para splash screen Android
- `apple-touch-icon.png` (180×180) — Para "Añadir a inicio" en iOS Safari

> 💡 Se pueden generar automáticamente desde el logo actual en `public/logo.webp`
> usando herramientas como [realfavicongenerator.net](https://realfavicongenerator.net)

---

## 📱 Fase 1B: Service Worker en `mobile/sw.ts` (1–2 días)

> **Impacto en webapp:** ✅ El SW solo funciona cuando está registrado. En desktop ignora las directivas móviles.

### 2.1 Crear `mobile/sw.ts`

```typescript
// mobile/sw.ts
// Service Worker con Serwist — compatible con Next.js 15+
import { defaultCache } from "@serwist/next/worker";
import { Serwist } from "serwist";

const serwist = new Serwist({
  precacheEntries: self.__SW_MANIFEST,
  skipWaiting: true,
  clientsClaim: true,
  navigationPreload: true,
  runtimeCaching: [
    ...defaultCache,
    // Cache de imágenes de propiedades (7 días)
    {
      matcher: /^https:\/\/.*\.(jpg|jpeg|png|webp|gif)$/i,
      handler: "CacheFirst",
      options: {
        cacheName: "sivarcasas-images",
        expiration: {
          maxEntries: 200,
          maxAgeSeconds: 60 * 60 * 24 * 7,
        },
      },
    },
    // Cache de API (5 minutos — NetworkFirst para datos frescos)
    {
      matcher: ({ url }) => url.pathname.startsWith("/api/"),
      handler: "NetworkFirst",
      options: {
        cacheName: "sivarcasas-api",
        expiration: {
          maxEntries: 50,
          maxAgeSeconds: 60 * 5,
        },
      },
    },
  ],
});

serwist.addEventListeners();
```

### 2.2 Cambio mínimo en `next.config.ts` — Reversible con 1 línea

Este es el **único cambio en archivos existentes**, y está diseñado para ser reversible con una sola variable:

```typescript
// next.config.ts — CAMBIO MÍNIMO Y REVERSIBLE

import type { NextConfig } from "next";
import path from "path";

// ✅ Control de PWA: si ENABLE_PWA=true, activa el Service Worker
// Si se comenta esta línea, el webapp funciona exactamente igual que antes
const ENABLE_PWA = process.env.ENABLE_PWA === 'true';

const emptyPolyfill = path.resolve(
  import.meta.dirname ?? __dirname,
  'src/empty-polyfills.js'
);

const baseConfig: NextConfig = {
  // ✅ output NO cambia — se mantiene SSR (no static export)
  experimental: {
    optimizePackageImports: ['react-leaflet', 'leaflet', 'echarts'],
    cssChunking: 'strict',
    optimizeCss: true,
  },
  turbopack: {
    resolveAlias: {
      'next/dist/build/polyfills/polyfill-nomodule': './src/empty-polyfills.js',
    },
  },
  webpack(config, { isServer }) {
    if (!isServer) {
      config.resolve.alias = {
        ...config.resolve.alias,
        'next/dist/build/polyfills/polyfill-nomodule': emptyPolyfill,
      };
    }
    return config;
  },
  images: {
    remotePatterns: [{ protocol: 'https', hostname: '**' }],
  },
  async redirects() {
    // ✅ Se mantienen intactas — incompatible con output:'export'
    const departments = [
      'ahuachapan', 'cabanas', 'chalatenango', 'cuscatlan',
      'la-libertad', 'la-paz', 'la-union', 'morazan',
      'san-miguel', 'san-salvador', 'san-vicente', 'santa-ana',
      'sonsonate', 'usulutan'
    ];
    return departments.flatMap(dept => [
      { source: `/tag/${dept}`, destination: `/${dept}`, permanent: true },
      { source: `/tag/${dept}/:filter`, destination: `/${dept}/:filter`, permanent: true },
    ]);
  },
};

// Aplicar wrapper PWA solo si está habilitado
// Para desactivar: eliminar el withSerwist o poner ENABLE_PWA=false en .env
let exportedConfig: NextConfig = baseConfig;

if (ENABLE_PWA) {
  const { withSerwist } = require("@serwist/next");
  exportedConfig = withSerwist({
    swSrc: "mobile/sw.ts",
    swDest: "public/sw.js",
  })(baseConfig);
}

export default exportedConfig;
```

> **Para desactivar PWA completamente y volver al webapp original:**
> ```
> # .env.local (no commitear)
> ENABLE_PWA=false
> ```

---

## 📱 Fase 2: Capacitor en `mobile/` (2–3 días)

> **Impacto en webapp:** ✅ Cero. Capacitor es una herramienta de build externa que envuelve el webapp.

### 3.1 Instalar dependencias

```bash
# Capacitor — solo para empaquetado nativo (no afecta el bundle web)
npm install @capacitor/cli @capacitor/core
npm install @capacitor/android @capacitor/ios
npm install @capacitor/splash-screen @capacitor/status-bar
npm install @capacitor/geolocation @capacitor/share
npm install @capacitor/push-notifications @capacitor/network

# Serwist para Service Worker
npm install @serwist/next serwist
```

### 3.2 Crear `mobile/capacitor.config.ts`

```typescript
// mobile/capacitor.config.ts
import { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.sivarcasas.app',
  appName: 'Sivarcasas',
  // ✅ ESTRATEGIA SERVIDOR VIVO: apunta al dominio de producción
  // Esto significa que el webapp SSR funciona sin ningún cambio
  server: {
    url: 'https://sivarcasas.com',   // ← Reemplazar con el dominio real
    cleartext: false,
    androidScheme: 'https',
  },
  // webDir solo se usa si se hace export estático en el futuro
  webDir: 'out',
  plugins: {
    SplashScreen: {
      launchShowDuration: 2000,
      launchAutoHide: true,
      backgroundColor: "#1e3a5f",
      androidSplashResourceName: "splash",
      androidScaleType: "CENTER_CROP",
      showSpinner: false,
      splashFullScreen: true,
      splashImmersive: true,
    },
    StatusBar: {
      style: 'LIGHT',
      backgroundColor: '#1e3a5f',
    },
    PushNotifications: {
      presentationOptions: ['badge', 'sound', 'alert'],
    },
  },
};

export default config;
```

> **Nota:** Copiar o hacer symlink a la raíz del proyecto para que Capacitor lo encuentre:
> ```bash
> # Copiar a la raíz (Windows no soporta symlinks fácilmente)
> copy mobile\capacitor.config.ts capacitor.config.ts
> ```

### 3.3 Inicializar plataformas nativas

```bash
npx cap init "Sivarcasas" "com.sivarcasas.app" --web-dir=out
npx cap add android
npx cap add ios
npx cap sync
```

---

## 📱 Fase 3: Hooks móviles en `mobile/hooks/` (2–3 días)

> **Impacto en webapp:** ✅ Cero. Estos hooks viven en `mobile/hooks/`, no en `src/hooks/`.
> Solo se importan desde componentes que elijan usarlos.

### 4.1 `mobile/hooks/usePlatform.ts`

```typescript
// mobile/hooks/usePlatform.ts
import { useEffect, useState } from 'react';

type Platform = 'web' | 'ios' | 'android';

export function usePlatform(): Platform {
  const [platform, setPlatform] = useState<Platform>('web');

  useEffect(() => {
    import('@capacitor/core').then(({ Capacitor }) => {
      if (Capacitor.isNativePlatform()) {
        setPlatform(Capacitor.getPlatform() as Platform);
      }
    }).catch(() => {
      // Si Capacitor no está disponible, permanece 'web'
    });
  }, []);

  return platform;
}
```

### 4.2 `mobile/hooks/useGeolocation.ts`

```typescript
// mobile/hooks/useGeolocation.ts
// Geolocalización con fallback: nativa → web API → null

export async function getCurrentLocation(): Promise<{ lat: number; lng: number } | null> {
  const isNative = typeof window !== 'undefined' &&
    (window as any).Capacitor?.isNativePlatform();

  if (isNative) {
    try {
      const { Geolocation } = await import('@capacitor/geolocation');
      const perms = await Geolocation.requestPermissions();
      if (perms.location !== 'granted') return null;

      const pos = await Geolocation.getCurrentPosition({ enableHighAccuracy: true, timeout: 10000 });
      return { lat: pos.coords.latitude, lng: pos.coords.longitude };
    } catch {
      return null;
    }
  }

  // Fallback web (para PWA en browser)
  return new Promise((resolve) => {
    if (!navigator.geolocation) { resolve(null); return; }
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
      () => resolve(null)
    );
  });
}
```

### 4.3 `mobile/hooks/useShare.ts`

```typescript
// mobile/hooks/useShare.ts
// Share nativo con fallback a Web Share API y clipboard

export async function shareListing(title: string, url: string): Promise<void> {
  const isNative = typeof window !== 'undefined' &&
    (window as any).Capacitor?.isNativePlatform();

  if (isNative) {
    const { Share } = await import('@capacitor/share');
    await Share.share({
      title,
      text: `Mira esta propiedad en Sivarcasas: ${title}`,
      url,
      dialogTitle: 'Compartir propiedad',
    });
    return;
  }

  // Fallback: Web Share API (Chrome móvil)
  if (navigator.share) {
    await navigator.share({ title, url });
    return;
  }

  // Fallback final: copiar al portapapeles
  await navigator.clipboard.writeText(url);
}
```

### 4.4 `mobile/hooks/usePushNotifications.ts`

```typescript
// mobile/hooks/usePushNotifications.ts
// Push notifications solo en plataformas nativas

export async function setupPushNotifications(
  onToken?: (token: string) => void
): Promise<void> {
  const isNative = typeof window !== 'undefined' &&
    (window as any).Capacitor?.isNativePlatform();

  if (!isNative) return;

  const { PushNotifications } = await import('@capacitor/push-notifications');
  const permission = await PushNotifications.requestPermissions();
  if (permission.receive !== 'granted') return;

  await PushNotifications.register();

  PushNotifications.addListener('registration', (token) => {
    console.log('Push token registrado:', token.value);
    onToken?.(token.value);
    // Aquí enviar el token al backend:
    // fetch('/api/push-token', { method: 'POST', body: JSON.stringify({ token: token.value }) });
  });

  PushNotifications.addListener('pushNotificationReceived', (notification) => {
    console.log('Notificación recibida:', notification.title);
  });
}
```

---

## 📱 Fase 4: Componentes móviles en `mobile/components/` (1–2 días)

> **Impacto en webapp:** ✅ Cero. Estos componentes son opcionales y solo se montan si se importan.

### 5.1 `mobile/components/MobileInstallBanner.tsx`

Banner que aparece solo en móvil cuando la app es instalable, sin afectar el desktop:

```tsx
// mobile/components/MobileInstallBanner.tsx
'use client';
import { useEffect, useState } from 'react';

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

export function MobileInstallBanner() {
  const [installEvent, setInstallEvent] = useState<BeforeInstallPromptEvent | null>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    const handler = (e: Event) => {
      e.preventDefault();
      setInstallEvent(e as BeforeInstallPromptEvent);
    };
    window.addEventListener('beforeinstallprompt', handler);
    return () => window.removeEventListener('beforeinstallprompt', handler);
  }, []);

  if (!installEvent || dismissed) return null;

  return (
    <div className="fixed bottom-4 left-4 right-4 z-50 flex items-center gap-3 rounded-2xl bg-[#1e3a5f] px-4 py-3 text-white shadow-2xl md:hidden">
      <span className="text-2xl">📱</span>
      <div className="flex-1">
        <p className="text-sm font-semibold">Instalar Sivarcasas</p>
        <p className="text-xs opacity-80">Acceso rápido desde tu pantalla de inicio</p>
      </div>
      <button
        onClick={async () => {
          await installEvent.prompt();
          setDismissed(true);
        }}
        className="rounded-lg bg-white px-3 py-1.5 text-xs font-bold text-[#1e3a5f]"
      >
        Instalar
      </button>
      <button onClick={() => setDismissed(true)} className="opacity-60 hover:opacity-100">✕</button>
    </div>
  );
}
```

### 5.2 `mobile/components/MobileSafeArea.tsx`

Wrapper para safe areas de iOS (notch, home bar) — solo activo en app nativa:

```tsx
// mobile/components/MobileSafeArea.tsx
'use client';
import { usePlatform } from '../hooks/usePlatform';

export function MobileSafeArea({ children }: { children: React.ReactNode }) {
  const platform = usePlatform();

  if (platform === 'web') return <>{children}</>;

  return (
    <div style={{
      paddingTop: 'env(safe-area-inset-top)',
      paddingBottom: 'env(safe-area-inset-bottom)',
      paddingLeft: 'env(safe-area-inset-left)',
      paddingRight: 'env(safe-area-inset-right)',
    }}>
      {children}
    </div>
  );
}
```

---

## 📱 Fase 5: CSS móvil en `mobile/styles/mobile.css` (0.5 días)

> **Impacto en webapp:** ✅ Cero. Este CSS **NO se agrega a `globals.css`**.
> Se importa únicamente desde componentes del módulo `mobile/`.

```css
/* mobile/styles/mobile.css */
/* Estilos exclusivos para la app nativa — NO importar en el webapp web */

/* Safe areas para iPhones con notch */
.mobile-safe-top    { padding-top:    env(safe-area-inset-top);    }
.mobile-safe-bottom { padding-bottom: env(safe-area-inset-bottom); }

/* Evitar zoom en inputs iOS (sistema iOS hace zoom en <16px) */
.mobile-input {
  font-size: 16px;
}

/* Scroll más fluido en iOS */
.mobile-scroll {
  -webkit-overflow-scrolling: touch;
  overflow-y: auto;
}

/* Tap highlight limpio (sin overlay gris en Android) */
.mobile-tap {
  -webkit-tap-highlight-color: transparent;
  touch-action: manipulation;
}

/* Selección de texto desactivada en elementos de UI */
.mobile-no-select {
  user-select: none;
  -webkit-user-select: none;
}
```

---

## 📱 Fase 6: Punto de entrada en `src/app/layout.tsx` (cambio mínimo, opcional)

> Este es el punto donde el módulo móvil "se conecta" al webapp.
> El cambio es **aditivo** (solo se agregan líneas, no se eliminan ni modifican las existentes).

**Opción A (recomendada): Agregar manifest sin tocar metadata existente**

Solo se agrega el link al manifest en el `<head>`. Esto es suficiente para activar la PWA:

```html
<!-- Agregar en src/app/layout.tsx dentro del <head>, sin tocar el resto -->
<link rel="manifest" href="/manifest.json" />
<link rel="apple-touch-icon" href="/icons/apple-touch-icon.png" />
<meta name="theme-color" content="#1e3a5f" />
```

Se puede hacer sin modificar el objeto `metadata` en absoluto, usando el `<head>` directamente en el layout:

```tsx
// src/app/layout.tsx — CAMBIO ADITIVO MÍNIMO
// Solo agregar estas 3 líneas dentro del <head>
// El resto del archivo permanece exactamente igual

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" suppressHydrationWarning>
      <head>
        {/* ↓ NUEVAS LÍNEAS — no modifican nada existente */}
        <link rel="manifest" href="/manifest.json" />
        <link rel="apple-touch-icon" href="/icons/apple-touch-icon.png" />
        <meta name="theme-color" content="#1e3a5f" />
      </head>
      <body className={inter.className}>
        <Providers>
          {children}
        </Providers>
        <SpeedInsights />
        <Analytics />
      </body>
    </html>
  );
}
```

**Opción B: NO tocar layout.tsx en absoluto**

Si no se quiere tocar `layout.tsx`, se pueden agregar las metas PWA directamente en `public/manifest.json` (ya hecho) y advertir al usuario que en Safari iOS el "Add to Home Screen" funciona sin `apple-touch-icon` si hay íconos en el manifest. Funcionalidad reducida pero cero riesgo.

---

## 📦 Scripts en `package.json` — Solo adiciones

```json
{
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "eslint",
    "cap:sync":        "npx cap sync",
    "cap:android":     "npx cap open android",
    "cap:ios":         "npx cap open ios",
    "cap:run:android": "npx cap run android",
    "cap:run:ios":     "npx cap run ios"
  }
}
```

> Los scripts `dev`, `build`, `start` y `lint` no cambian. Solo se **agregan** los scripts `cap:*`.

---

## 📱 Fase 7: Testing (3–4 días)

### Checklist PWA — Sin afectar webapp

- [ ] `public/manifest.json` accesible en `/manifest.json`
- [ ] Íconos visibles en `/icons/`
- [ ] Chrome DevTools → Application → Manifest: sin errores
- [ ] Lighthouse PWA Score > 90 (en móvil)
- [ ] "Instalar app" aparece en Chrome Android
- [ ] "Añadir a inicio" funciona en Safari iOS
- [ ] Service Worker activo en DevTools → Application → Service Workers
- [ ] Webapp desktop sin cambios (abrir en Chrome desktop y verificar)

### Checklist Capacitor Android

```bash
copy mobile\capacitor.config.ts capacitor.config.ts
npx cap sync android
npx cap run android
```

- [ ] App abre correctamente (carga el servidor vivo)
- [ ] SplashScreen aparece 2 segundos
- [ ] StatusBar con color correcto
- [ ] Geolocalización solicita permiso
- [ ] Botón atrás de Android funciona
- [ ] Share nativo funciona

### Checklist Capacitor iOS (requiere Mac con Xcode)

```bash
copy mobile\capacitor.config.ts capacitor.config.ts
npx cap sync ios
npx cap open ios  # Abrir en Xcode (en Mac)
```

- [ ] App abre en simulador
- [ ] Safe areas respetadas (notch, home bar)
- [ ] Geolocalización solicita permiso con texto en español
- [ ] Push notifications recibidas

---

## 📱 Fase 8: Stores (8–12 días)

### Google Play Store

1. Crear cuenta developer → **$25 una sola vez** → [play.google.com/console](https://play.google.com/console)
2. Generar AAB firmado:
   ```bash
   npx cap open android
   # En Android Studio: Build > Generate Signed Bundle / APK > Android App Bundle
   ```
3. Subir AAB + completar listing + enviar revisión
4. **Tiempo revisión:** 1–3 días hábiles

### Apple App Store

1. Cuenta Apple Developer → **$99/año** → [developer.apple.com](https://developer.apple.com)
2. Compilar desde Xcode en Mac: Product > Archive > Distribute App
3. Completar metadata en App Store Connect + Privacy Policy URL
4. **Tiempo revisión:** 1–7 días

> ⚠️ **Apple rechaza apps "wrapper" puro**. El plan usa Geolocalización + Share nativo + Push, lo que califica como app nativa legítima.

> ⚠️ **iOS requiere Mac con Xcode**. No es posible compilar para iOS desde Windows. Alternativas: MacStadium (cloud Mac), GitHub Actions con macOS runner.

> ⚠️ **Guardar el keystore de Android en lugar seguro**. Si se pierde, no se puede actualizar la app en Play Store. Usar gestor de contraseñas o repositorio privado cifrado.

---

## 🗓️ Timeline Total

| Fase | Duración | Impacto en Webapp |
|------|----------|-------------------|
| 1A — Archivos PWA en `public/` | 1–2 días | ✅ Ninguno |
| 1B — Service Worker en `mobile/sw.ts` | 1–2 días | ✅ Mínimo (1 línea opt-in en `.env`) |
| 2 — Capacitor config en `mobile/` | 1–2 días | ✅ Ninguno |
| 3 — Hooks móviles en `mobile/hooks/` | 2–3 días | ✅ Ninguno |
| 4 — Componentes en `mobile/components/` | 1–2 días | ✅ Ninguno |
| 5 — CSS en `mobile/styles/` | 0.5 días | ✅ Ninguno |
| 6 — Punto de entrada en `layout.tsx` | 0.5 días | 🟡 Mínimo (3 líneas aditivas) |
| 7 — Testing | 3–4 días | ✅ Ninguno |
| 8 — Stores | 8–12 días | ✅ Ninguno |

**Total: 18–29 días (~4 semanas)**

---

## 📋 Checklist de Archivos

### Archivos que se CREAN (nuevos):
- [ ] `public/manifest.json`
- [ ] `public/icons/icon-192x192.png`
- [ ] `public/icons/icon-512x512.png`
- [ ] `public/icons/apple-touch-icon.png`
- [ ] `mobile/README.md`
- [ ] `mobile/sw.ts`
- [ ] `mobile/capacitor.config.ts`
- [ ] `mobile/hooks/usePlatform.ts`
- [ ] `mobile/hooks/useGeolocation.ts`
- [ ] `mobile/hooks/useShare.ts`
- [ ] `mobile/hooks/usePushNotifications.ts`
- [ ] `mobile/components/MobileInstallBanner.tsx`
- [ ] `mobile/components/MobileSafeArea.tsx`
- [ ] `mobile/styles/mobile.css`
- [ ] `capacitor.config.ts` (copia de `mobile/capacitor.config.ts` en raíz)

### Archivos existentes modificados (cambios aditivos únicamente):
- [ ] `next.config.ts` — Wrapper `withSerwist` condicional vía `ENABLE_PWA=true`
- [ ] `package.json` — Agregar scripts `cap:*` y dependencias móviles
- [ ] `src/app/layout.tsx` — Agregar 3 líneas `<link>` y `<meta>` en `<head>`

### Archivos que NO se tocan:
- ❌ `src/app/globals.css` — Sin cambios
- ❌ `src/app/page.tsx` — Sin cambios
- ❌ `src/hooks/` — Sin cambios
- ❌ `src/components/` — Sin cambios
- ❌ `src/lib/` — Sin cambios
- ❌ Todas las páginas de rutas — Sin cambios
