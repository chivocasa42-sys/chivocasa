'use client';

import dynamic from 'next/dynamic';
import Navbar from '@/components/Navbar';

const MapExplorer = dynamic(() => import('@/components/MapExplorer'), {
  ssr: false,
  loading: () => (
    <div className="w-full rounded-2xl border border-[#e2e8f0] bg-[var(--bg-card)] overflow-hidden mb-8" style={{ height: '500px' }}>
      <div className="skeleton-pulse w-full h-full" />
    </div>
  ),
});

export default function LocationExplorerClient() {
  return (
    <>
      <Navbar onRefresh={() => window.location.reload()} />

      <main className="mx-auto w-full max-w-[1800px] px-4 pb-6 pt-6 sm:px-6 xl:px-8">
        <MapExplorer />
      </main>
    </>
  );
}
