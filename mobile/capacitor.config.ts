// mobile/capacitor.config.ts
// Configuración de Capacitor para la app nativa de Sivarcasas
//
// ESTRATEGIA: Servidor Vivo (no static export)
// La app nativa carga el webapp SSR desde el servidor de producción.
// Esto mantiene SSR, rutas dinámicas y todas las features del webapp intactas.
//
// IMPORTANTE: Copiar este archivo a la raíz del proyecto antes de ejecutar cap commands:
//   Windows: copy mobile\capacitor.config.ts capacitor.config.ts
//   Mac/Linux: cp mobile/capacitor.config.ts capacitor.config.ts

import { CapacitorConfig } from '@capacitor/cli';

const isDev = process.env.CAP_ENV === 'development';

const config: CapacitorConfig = {
  appId: 'com.sivarcasas.app',
  appName: 'Sivarcasas',

  // En modo desarrollo, apunta al servidor local
  // En producción, apunta al dominio real
  server: isDev
    ? {
        // Cambiar 192.168.1.X por la IP local de tu máquina
        // Para obtenerla en Windows: ipconfig | encontrar "IPv4"
        url: 'http://192.168.40.90:3000',
        cleartext: true,
        androidScheme: 'http',
      }
    : {
        url: 'https://sivarcasas.com', // ← Cambiar por el dominio real en producción
        cleartext: false,
        androidScheme: 'https',
      },

  // webDir se usará en el futuro si se implementa modo offline con static export
  webDir: 'out',

  plugins: {
    SplashScreen: {
      launchShowDuration: 2000,
      launchAutoHide: true,
      backgroundColor: '#1e3a5f',
      androidSplashResourceName: 'splash',
      androidScaleType: 'CENTER_CROP',
      showSpinner: false,
      splashFullScreen: true,
      splashImmersive: true,
    },

    StatusBar: {
      style: 'LIGHT',     // Íconos blancos sobre barra oscura
      backgroundColor: '#1e3a5f',
    },

    PushNotifications: {
      presentationOptions: ['badge', 'sound', 'alert'],
    },

    // Configuración de permisos de geolocalización (iOS)
    // Los textos se muestran al usuario cuando la app solicita permisos
    Geolocation: {
      // Estos permisos también se configuran en Info.plist de iOS
    },
  },
};

export default config;
