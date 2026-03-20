'use client';

import { useEffect, useState, useCallback, useRef } from 'react';

/* ────────────────────────────────────────────────────────────────────
 * PWAInstallPrompt
 *
 * • Android / Chrome:  Captures `beforeinstallprompt`, shows a
 *   floating banner with an "Instalar" button.
 * • iOS Safari:        Detects iOS + non-standalone and shows
 *   step-by-step instructions in Spanish.
 * • Already installed: Renders nothing.
 * • Dismissals are stored in localStorage for 7 days.
 * ──────────────────────────────────────────────────────────────────── */

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

const DISMISS_KEY = 'pwa-install-dismissed';
const DISMISS_DAYS = 7;

function wasDismissed(): boolean {
  if (typeof window === 'undefined') return false;
  try {
    const raw = localStorage.getItem(DISMISS_KEY);
    if (!raw) return false;
    const ts = Number(raw);
    return Date.now() - ts < DISMISS_DAYS * 86_400_000;
  } catch {
    return false;
  }
}

function setDismissed(): void {
  try {
    localStorage.setItem(DISMISS_KEY, String(Date.now()));
  } catch {
    /* storage full — silently ignore */
  }
}

function isIOS(): boolean {
  if (typeof navigator === 'undefined') return false;
  return (
    /iPad|iPhone|iPod/.test(navigator.userAgent) ||
    (navigator.userAgent.includes('Mac') && 'ontouchend' in document)
  );
}

function isStandalone(): boolean {
  if (typeof window === 'undefined') return false;
  return (
    window.matchMedia('(display-mode: standalone)').matches ||
    ('standalone' in navigator && (navigator as unknown as { standalone: boolean }).standalone === true)
  );
}

export default function PWAInstallPrompt() {
  const [showAndroid, setShowAndroid] = useState(false);
  const [showIOS, setShowIOS] = useState(false);
  const deferredPrompt = useRef<BeforeInstallPromptEvent | null>(null);

  /* ── Android: listen for beforeinstallprompt ──────────────────── */
  useEffect(() => {
    if (isStandalone() || wasDismissed()) return;

    const handler = (e: Event) => {
      e.preventDefault();
      deferredPrompt.current = e as BeforeInstallPromptEvent;
      setShowAndroid(true);
    };

    window.addEventListener('beforeinstallprompt', handler);
    return () => window.removeEventListener('beforeinstallprompt', handler);
  }, []);

  /* ── iOS: detect Safari + not standalone ──────────────────────── */
  useEffect(() => {
    if (isStandalone() || wasDismissed()) return;
    if (isIOS()) setShowIOS(true);
  }, []);

  /* ── Handlers ─────────────────────────────────────────────────── */
  const handleInstall = useCallback(async () => {
    const prompt = deferredPrompt.current;
    if (!prompt) return;
    await prompt.prompt();
    const { outcome } = await prompt.userChoice;
    if (outcome === 'accepted') {
      setShowAndroid(false);
    }
    deferredPrompt.current = null;
  }, []);

  const handleDismiss = useCallback(() => {
    setDismissed();
    setShowAndroid(false);
    setShowIOS(false);
  }, []);

  /* ── Don't render anything if nothing to show ─────────────────── */
  if (!showAndroid && !showIOS) return null;

  return (
    <div
      style={{
        position: 'fixed',
        bottom: '1rem',
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 9999,
        width: 'calc(100% - 2rem)',
        maxWidth: '420px',
      }}
    >
      <div
        style={{
          background: 'rgba(23, 23, 23, 0.95)',
          backdropFilter: 'blur(12px)',
          WebkitBackdropFilter: 'blur(12px)',
          border: '1px solid rgba(16, 185, 129, 0.25)',
          borderRadius: '16px',
          padding: '1rem 1.25rem',
          boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
          display: 'flex',
          alignItems: 'flex-start',
          gap: '0.75rem',
          color: '#e5e5e5',
          fontFamily: "'Inter', system-ui, sans-serif",
          fontSize: '0.875rem',
          lineHeight: 1.5,
        }}
      >
        {/* Icon */}
        <img
          src="/icons/android-chrome-192x192.png"
          alt="sivarcasas"
          width={44}
          height={44}
          style={{ borderRadius: '10px', flexShrink: 0 }}
        />

        <div style={{ flex: 1, minWidth: 0 }}>
          {/* ── Android Banner ──────────────────────────────────── */}
          {showAndroid && (
            <>
              <p style={{ fontWeight: 600, marginBottom: '0.25rem' }}>
                Instalar sivarcasas
              </p>
              <p style={{ color: '#a3a3a3', fontSize: '0.8rem', marginBottom: '0.75rem' }}>
                Accedé más rápido desde tu pantalla de inicio.
              </p>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button
                  onClick={handleInstall}
                  style={{
                    background: '#10b981',
                    color: '#0a0a0a',
                    border: 'none',
                    borderRadius: '8px',
                    padding: '0.5rem 1rem',
                    fontWeight: 600,
                    fontSize: '0.8rem',
                    cursor: 'pointer',
                  }}
                >
                  Instalar
                </button>
                <button
                  onClick={handleDismiss}
                  style={{
                    background: 'transparent',
                    color: '#a3a3a3',
                    border: '1px solid rgba(163,163,163,0.3)',
                    borderRadius: '8px',
                    padding: '0.5rem 1rem',
                    fontSize: '0.8rem',
                    cursor: 'pointer',
                  }}
                >
                  Ahora no
                </button>
              </div>
            </>
          )}

          {/* ── iOS Instructions ────────────────────────────────── */}
          {showIOS && !showAndroid && (
            <>
              <p style={{ fontWeight: 600, marginBottom: '0.25rem' }}>
                Agregá sivarcasas a tu inicio
              </p>
              <p style={{ color: '#a3a3a3', fontSize: '0.8rem', marginBottom: '0.5rem' }}>
                Tocá{' '}
                <span
                  role="img"
                  aria-label="compartir"
                  style={{ fontSize: '1rem', verticalAlign: 'middle' }}
                >
                  ⎙
                </span>{' '}
                <strong>Compartir</strong> y luego{' '}
                <strong>&quot;Agregar a pantalla de inicio&quot;</strong>.
              </p>
              <button
                onClick={handleDismiss}
                style={{
                  background: 'transparent',
                  color: '#a3a3a3',
                  border: '1px solid rgba(163,163,163,0.3)',
                  borderRadius: '8px',
                  padding: '0.4rem 0.75rem',
                  fontSize: '0.75rem',
                  cursor: 'pointer',
                }}
              >
                Entendido
              </button>
            </>
          )}
        </div>

        {/* Close button */}
        <button
          onClick={handleDismiss}
          aria-label="Cerrar"
          style={{
            background: 'none',
            border: 'none',
            color: '#636363',
            fontSize: '1.25rem',
            cursor: 'pointer',
            padding: '0',
            lineHeight: 1,
            flexShrink: 0,
          }}
        >
          ✕
        </button>
      </div>
    </div>
  );
}
