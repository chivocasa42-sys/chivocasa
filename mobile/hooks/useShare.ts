// mobile/hooks/useShare.ts
// Compartir propiedades con fallback automático:
//   Plataforma nativa → @capacitor/share (sheet nativo del SO)
//   Browser móvil    → Web Share API (Chrome/Safari móvil)
//   Escritorio       → Copiar enlace al portapapeles

export interface ShareOptions {
  title: string;
  text?: string;
  url: string;
}

export async function shareListing(options: ShareOptions): Promise<'shared' | 'copied' | 'error'> {
  const { title, text, url } = options;
  const shareText = text ?? `Mira esta propiedad en Sivarcasas: ${title}`;

  const isNative =
    typeof window !== 'undefined' &&
    (window as any).Capacitor?.isNativePlatform();

  // 1. Plataforma nativa (Android / iOS via Capacitor)
  if (isNative) {
    try {
      const { Share } = await import('@capacitor/share');
      await Share.share({
        title,
        text: shareText,
        url,
        dialogTitle: 'Compartir propiedad',
      });
      return 'shared';
    } catch (err) {
      console.warn('[Sivarcasas Mobile] Error en share nativo:', err);
      return 'error';
    }
  }

  // 2. Web Share API (Chrome Android / Safari iOS en browser)
  if (typeof navigator !== 'undefined' && navigator.share) {
    try {
      await navigator.share({ title, text: shareText, url });
      return 'shared';
    } catch (err) {
      // El usuario canceló el share — no es un error
      return 'error';
    }
  }

  // 3. Fallback: copiar al portapapeles (desktop)
  try {
    await navigator.clipboard.writeText(url);
    return 'copied';
  } catch {
    return 'error';
  }
}
