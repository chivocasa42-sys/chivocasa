// mobile/hooks/usePushNotifications.ts
// Configuración de Push Notifications vía Capacitor.
// Solo se activa en plataformas nativas (iOS / Android).
// En el browser no hace nada (no lanza errores).

export interface PushSetupOptions {
  /** Callback que recibe el token de registro para enviarlo al backend */
  onToken?: (token: string) => void;
  /** Callback cuando se recibe una notificación en primer plano */
  onNotificationReceived?: (title: string, body: string) => void;
}

export async function setupPushNotifications(
  options: PushSetupOptions = {}
): Promise<boolean> {
  const isNative =
    typeof window !== 'undefined' &&
    (window as any).Capacitor?.isNativePlatform();

  if (!isNative) return false;

  try {
    const { PushNotifications } = await import('@capacitor/push-notifications');

    // Solicitar permiso
    const permission = await PushNotifications.requestPermissions();
    if (permission.receive !== 'granted') {
      console.warn('[Sivarcasas Mobile] Push notifications: permiso denegado');
      return false;
    }

    // Registrar dispositivo
    await PushNotifications.register();

    // Escuchar token de registro
    PushNotifications.addListener('registration', (token) => {
      console.log('[Sivarcasas Mobile] Push token:', token.value);
      options.onToken?.(token.value);

      // Enviar token al backend para almacenar
      // Descomentar cuando el endpoint esté listo:
      // fetch('/api/push-token', {
      //   method: 'POST',
      //   headers: { 'Content-Type': 'application/json' },
      //   body: JSON.stringify({ token: token.value }),
      // }).catch(console.error);
    });

    // Error de registro
    PushNotifications.addListener('registrationError', (err) => {
      console.error('[Sivarcasas Mobile] Error registrando push:', err.error);
    });

    // Notificación recibida con app abierta (primer plano)
    PushNotifications.addListener('pushNotificationReceived', (notification) => {
      console.log('[Sivarcasas Mobile] Notificación:', notification.title);
      if (notification.title && notification.body) {
        options.onNotificationReceived?.(notification.title, notification.body);
      }
    });

    // Notificación tocada (app en segundo plano o cerrada)
    PushNotifications.addListener('pushNotificationActionPerformed', (action) => {
      console.log('[Sivarcasas Mobile] Notificación tocada:', action.notification.title);
      // Aquí se puede navegar a una ruta específica según la notificación:
      // const data = action.notification.data;
      // if (data?.listingId) router.push(`/inmuebles/${data.listingId}`);
    });

    return true;
  } catch (err) {
    console.error('[Sivarcasas Mobile] Error configurando push notifications:', err);
    return false;
  }
}
