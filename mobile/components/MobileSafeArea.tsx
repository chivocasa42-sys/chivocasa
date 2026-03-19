'use client';
// mobile/components/MobileSafeArea.tsx
// Wrapper que aplica padding de safe areas de iOS (notch, Dynamic Island, home bar).
// En web normal no agrega padding — es un passthrough transparente.

import { usePlatform } from '../hooks/usePlatform';

interface MobileSafeAreaProps {
  children: React.ReactNode;
  /** Si true, aplica safe-area solo en la parte superior */
  topOnly?: boolean;
  /** Si true, aplica safe-area solo en la parte inferior */
  bottomOnly?: boolean;
}

export function MobileSafeArea({
  children,
  topOnly = false,
  bottomOnly = false,
}: MobileSafeAreaProps) {
  const platform = usePlatform();

  // En web browser, no aplicar padding — renderizar children tal cual
  if (platform === 'web') return <>{children}</>;

  const style: React.CSSProperties = {};

  if (!bottomOnly) style.paddingTop = 'env(safe-area-inset-top)';
  if (!topOnly) style.paddingBottom = 'env(safe-area-inset-bottom)';

  // Siempre aplicar izquierda/derecha (landscape mode en iPhone)
  if (!topOnly && !bottomOnly) {
    style.paddingLeft = 'env(safe-area-inset-left)';
    style.paddingRight = 'env(safe-area-inset-right)';
  }

  return <div style={style}>{children}</div>;
}
