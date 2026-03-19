# Módulo Mobile — Sivarcasas

Este directorio contiene **todo el código relacionado con la app móvil** (PWA + Capacitor).
Está diseñado para ser completamente **aislado del webapp web** — ningún archivo de `src/`
importa desde aquí, salvo los puntos de entrada explícitamente documentados abajo.

## Estructura

```
mobile/
├── sw.ts                          # Service Worker (compilado a public/sw.js)
├── capacitor.config.ts            # Configuración de Capacitor
├── hooks/
│   ├── usePlatform.ts             # Detecta si es web / iOS / Android
│   ├── useGeolocation.ts          # GPS nativo con fallback web
│   ├── useShare.ts                # Share nativo con fallback clipboard
│   └── usePushNotifications.ts   # Push notifications (solo nativo)
├── components/
│   ├── MobileInstallBanner.tsx    # Banner "Instalar app" para PWA
│   └── MobileSafeArea.tsx         # Wrapper de safe areas para iPhone
└── styles/
    └── mobile.css                 # CSS exclusivo para la app nativa
```

## Puntos de entrada al webapp

Solo dos archivos existentes del webapp tienen integración con este módulo:

| Archivo existente | Cambio |
|---|---|
| `next.config.ts` | Wrapper `withSerwist` activado por `ENABLE_PWA=true` |
| `src/app/layout.tsx` | 3 líneas `<link>` / `<meta>` para manifest y theme color |

## Activar PWA (Service Worker)

```bash
# Crear .env.local (no commitear) con:
ENABLE_PWA=true

# Luego hacer build:
npm run build
```

## Comandos Capacitor

Antes de cualquier comando `cap`, copiar la config a la raíz:

```powershell
# Windows
copy mobile\capacitor.config.ts capacitor.config.ts
```

```bash
# Modo desarrollo (apunta a servidor local)
$env:CAP_ENV="development"
copy mobile\capacitor.config.ts capacitor.config.ts
npx cap run android

# Modo producción (apunta a sivarcasas.com)
copy mobile\capacitor.config.ts capacitor.config.ts
npx cap sync
npx cap open android    # Android Studio
npx cap open ios        # Xcode (requiere Mac)
```

## Notas importantes

- **iOS require Mac con Xcode** para compilar. No se puede compilar para iOS desde Windows.
- **Guardar el keystore de Android** (generado en Android Studio) en un lugar seguro. Si se pierde, no se puede publicar actualizaciones.
- **El servidor debe estar disponible** en producción — la app nativa no tiene modo offline (ver plan de migración para Fase 2+).
