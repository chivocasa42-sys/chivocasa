# PWA — Documentación de implementación

## Qué se implementó

SivarCasas ahora es una **Progressive Web App instalable** usando capacidades nativas de Next.js App Router, sin dependencias adicionales.

| Componente | Archivo | Descripción |
|---|---|---|
| Manifest | `src/app/manifest.ts` | Genera `/manifest.webmanifest` automáticamente (Next.js nativo) |
| Service Worker | `public/sw.js` | Cachea solo assets estáticos; **nunca cachea API ni datos dinámicos** |
| Registro SW | `src/components/ServiceWorkerRegistrar.tsx` | Registra el SW solo en producción |
| Install UX | `src/components/PWAInstallPrompt.tsx` | Banner de instalación (Android) + instrucciones (iOS) |
| Offline | `public/offline.html` | Página de fallback cuando no hay conexión |
| Íconos | `public/icons/` | 192x192, 512x512, apple-touch-icon, favicons |
| Metadata | `src/app/layout.tsx` | `appleWebApp`, `icons`, `viewport.themeColor` |

---

## Estrategia de caché del Service Worker

| ✅ SÍ se cachea | ❌ NO se cachea |
|---|---|
| `/_next/static/*` (JS, CSS) | `/api/*` (todas las rutas) |
| `/icons/*` | Tiles de mapa (OpenStreetMap) |
| Google Fonts | Nominatim (geocoding) |
| `/offline.html` | Requests POST/PUT/DELETE |
| | Páginas de inmuebles individuales |

**Navegación**: Network-first con fallback a `/offline.html`.

---

## Cómo probar la instalación

### En Android (Chrome)
1. Abrí `https://sivarcasas.com` en Chrome
2. Debería aparecer un banner verde "Instalar sivarcasas" en la parte inferior
3. Tocá **Instalar** → se instala como app
4. También podés usar el menú ⋮ → "Instalar app" o "Agregar a pantalla de inicio"
5. La app abre en modo standalone (sin barra de navegación del browser)

### En iPhone (Safari)
1. Abrí `https://sivarcasas.com` en **Safari** (no Chrome)
2. Aparecerá un banner con instrucciones
3. Tocá el ícono de **Compartir** (⎙) en la barra inferior
4. Seleccioná **"Agregar a pantalla de inicio"**
5. Confirmá el nombre y tocá **Agregar**
6. La app aparece como ícono en tu pantalla de inicio

### Verificación local (desarrollo)
```bash
npm run build
npm run start
# Abrir http://localhost:3000 en Chrome
# DevTools → Application → Manifest (verificar datos)
# DevTools → Application → Service Workers (verificar registro)
```

> **Nota:** El service worker solo se registra en producción (`NODE_ENV === 'production'`). Usá `npm run start` (no `npm run dev`) para probarlo localmente.

---

## Limitaciones actuales

1. **iOS Safari**: No soporta `beforeinstallprompt` — se muestran instrucciones manuales.
2. **Push notifications**: No implementadas (no son necesarias para el caso de uso actual).
3. **Offline completo**: Solo se muestra la página offline de fallback. Las páginas individuales no se cachean para evitar mostrar datos desactualizados.
4. **Ícono maskable**: Usa el mismo ícono 512x512. Para un resultado óptimo en Android, se recomienda generar un ícono con safe zone adaptado.

---

## Dependencias agregadas

**Ninguna.** Todo se implementó con:
- `app/manifest.ts` → capacidad nativa de Next.js App Router
- Vanilla JavaScript para el service worker
- React `useEffect` + `useState` para el registro y UI de instalación
