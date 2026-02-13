'use client';

import { ReactNode } from 'react';
import { FavoritesProvider } from '@/hooks/useFavorites';

export default function Providers({ children }: { children: ReactNode }) {
    return (
        <FavoritesProvider>
            {children}
        </FavoritesProvider>
    );
}
