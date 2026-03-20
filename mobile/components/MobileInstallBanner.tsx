'use client';
// mobile/components/MobileInstallBanner.tsx
// Banner de instalación PWA — visible solo en móvil cuando la app es instalable.
// No afecta el webapp de escritorio (filtrado por breakpoint md: de Tailwind y por evento).

import { useEffect, useState } from 'react';

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

const DISMISS_KEY = 'sivarcasas_install_dismissed';

export function MobileInstallBanner() {
  const [installEvent, setInstallEvent] = useState<BeforeInstallPromptEvent | null>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    // No mostrar si ya fue descartado anteriormente
    if (sessionStorage.getItem(DISMISS_KEY)) return;

    const handler = (e: Event) => {
      e.preventDefault();
      setInstallEvent(e as BeforeInstallPromptEvent);
      setVisible(true);
    };

    window.addEventListener('beforeinstallprompt', handler);
    return () => window.removeEventListener('beforeinstallprompt', handler);
  }, []);

  if (!visible || !installEvent) return null;

  const handleInstall = async () => {
    await installEvent.prompt();
    const result = await installEvent.userChoice;
    if (result.outcome === 'accepted') {
      setVisible(false);
    }
  };

  const handleDismiss = () => {
    sessionStorage.setItem(DISMISS_KEY, '1');
    setVisible(false);
  };

  return (
    // md:hidden → solo visible en pantallas menores a 768px (móvil)
    <div className="fixed bottom-4 left-4 right-4 z-50 flex items-center gap-3 rounded-2xl bg-[#1e3a5f] px-4 py-3 text-white shadow-2xl md:hidden">
      <span className="text-2xl" aria-hidden="true">📱</span>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold truncate">Instalar Sivarcasas</p>
        <p className="text-xs opacity-80 truncate">Acceso rápido desde tu pantalla de inicio</p>
      </div>
      <button
        onClick={handleInstall}
        className="shrink-0 rounded-lg bg-white px-3 py-1.5 text-xs font-bold text-[#1e3a5f] hover:bg-gray-100 transition-colors"
        aria-label="Instalar aplicación"
      >
        Instalar
      </button>
      <button
        onClick={handleDismiss}
        className="shrink-0 opacity-60 hover:opacity-100 transition-opacity text-lg leading-none"
        aria-label="Cerrar banner"
      >
        ✕
      </button>
    </div>
  );
}
