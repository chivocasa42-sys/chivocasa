'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import Script from 'next/script';
import { useRouter } from 'next/navigation';
import SectionHeader from './SectionHeader';
import {
  computeRankings,
  toExpensiveDataPoints,
  toCheapDataPoints,
  toActiveDataPoints,
  type DepartmentStats,
} from '@/lib/rankingChartsAdapter';

declare global {
  interface Window {
    MarketRankingCharts: {
      initCharts: (config: Record<string, unknown>) => boolean;
      updateAllCharts: (expensive: unknown[], cheap: unknown[], active: unknown[]) => void;
      destroyCharts: () => void;
      observeSection: (id: string, onVisible: () => void, onHidden: () => void) => void;
      disconnectObserver: () => void;
      isReady: () => boolean;
    };
    echarts: unknown;
  }
}

interface MarketRankingChartsProps {
  departments: DepartmentStats[];
}

const REFRESH_INTERVAL_MS = 30_000;
const SECTION_ID = 'market-ranking-charts-section';

export default function MarketRankingCharts({ departments }: MarketRankingChartsProps) {
  const router = useRouter();
  const [status, setStatus] = useState<'idle' | 'loading' | 'ready' | 'error' | 'empty'>('idle');
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [secondsAgo, setSecondsAgo] = useState(0);

  const chartsInitialized = useRef(false);
  const isVisible = useRef(false);
  const pollingTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const tickTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const echartsLoaded = useRef(false);
  const interopLoaded = useRef(false);
  const initialDataRendered = useRef(false);

  // Navigate on bar click
  const handleBarClick = useCallback((slug: string) => {
    router.push(`/${slug}`);
  }, [router]);

  // Render charts with current data
  const renderCharts = useCallback((depts: DepartmentStats[]) => {
    if (!window.MarketRankingCharts || !window.MarketRankingCharts.isReady()) return false;

    const { topExpensive, topCheap, topActive } = computeRankings(depts);

    if (topExpensive.length === 0 && topCheap.length === 0 && topActive.length === 0) {
      setStatus('empty');
      return false;
    }

    const expData = toExpensiveDataPoints(topExpensive);
    const cheapData = toCheapDataPoints(topCheap);
    const activeData = toActiveDataPoints(topActive);

    if (!chartsInitialized.current) {
      const success = window.MarketRankingCharts.initCharts({
        containerIds: ['chart-expensive', 'chart-cheap', 'chart-active'],
        expensiveData: expData,
        cheapData: cheapData,
        activeData: activeData,
        onBarClick: handleBarClick,
      });

      if (success) {
        chartsInitialized.current = true;
        setStatus('ready');
        setLastUpdated(new Date());
        setSecondsAgo(0);
        return true;
      }
      return false;
    } else {
      window.MarketRankingCharts.updateAllCharts(expData, cheapData, activeData);
      setLastUpdated(new Date());
      setSecondsAgo(0);
      return true;
    }
  }, [handleBarClick]);

  // Fetch fresh data from API
  const fetchAndUpdate = useCallback(async () => {
    try {
      const res = await fetch('/api/department-stats');
      if (!res.ok) throw new Error('Failed to fetch');
      const data: DepartmentStats[] = await res.json();
      renderCharts(data);
    } catch {
      if (!chartsInitialized.current) {
        setStatus('error');
      }
      // If charts already rendered, silently skip failed refresh
    }
  }, [renderCharts]);

  // Start polling
  const startPolling = useCallback(() => {
    if (pollingTimer.current) return;
    pollingTimer.current = setInterval(() => {
      if (isVisible.current) {
        fetchAndUpdate();
      }
    }, REFRESH_INTERVAL_MS);
  }, [fetchAndUpdate]);

  // Stop polling
  const stopPolling = useCallback(() => {
    if (pollingTimer.current) {
      clearInterval(pollingTimer.current);
      pollingTimer.current = null;
    }
  }, []);

  // Try to initialize charts when both scripts are loaded
  const tryInit = useCallback(() => {
    if (!echartsLoaded.current || !interopLoaded.current) return;
    if (!isVisible.current) return;
    if (initialDataRendered.current) return;

    setStatus('loading');

    // Use passed departments for first render (avoids extra fetch)
    if (departments.length > 0) {
      const ok = renderCharts(departments);
      if (ok) {
        initialDataRendered.current = true;
        startPolling();
      }
    } else {
      // Fallback: fetch from API
      fetchAndUpdate().then(() => {
        initialDataRendered.current = true;
        startPolling();
      });
    }
  }, [departments, renderCharts, fetchAndUpdate, startPolling]);

  // Handle ECharts CDN load
  const onEChartsLoad = useCallback(() => {
    echartsLoaded.current = true;
    tryInit();
  }, [tryInit]);

  // Handle interop script load
  const onInteropLoad = useCallback(() => {
    interopLoaded.current = true;
    tryInit();
  }, [tryInit]);

  // Setup IntersectionObserver after mount
  useEffect(() => {
    const checkAndObserve = () => {
      const el = document.getElementById(SECTION_ID);
      if (!el) return;

      const obs = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              isVisible.current = true;
              tryInit();
              startPolling();
            } else {
              isVisible.current = false;
              stopPolling();
            }
          });
        },
        { threshold: 0.3 }
      );

      obs.observe(el);

      return () => {
        obs.disconnect();
      };
    };

    const cleanup = checkAndObserve();

    return () => {
      cleanup?.();
      stopPolling();
      if (chartsInitialized.current && window.MarketRankingCharts) {
        window.MarketRankingCharts.destroyCharts();
        chartsInitialized.current = false;
      }
    };
  }, [tryInit, startPolling, stopPolling]);

  // "Updated X seconds ago" ticker
  useEffect(() => {
    tickTimer.current = setInterval(() => {
      if (lastUpdated) {
        setSecondsAgo(Math.round((Date.now() - lastUpdated.getTime()) / 1000));
      }
    }, 1000);

    return () => {
      if (tickTimer.current) clearInterval(tickTimer.current);
    };
  }, [lastUpdated]);

  // Retry handler
  const handleRetry = () => {
    setStatus('loading');
    initialDataRendered.current = false;
    chartsInitialized.current = false;
    tryInit();
  };

  return (
    <>
      {/* Apache ECharts CDN — lazy loaded, no watermark */}
      <Script
        src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"
        strategy="lazyOnload"
        onLoad={onEChartsLoad}
      />
      {/* Interop script */}
      <Script
        src="/js/marketRankingCharts.js"
        strategy="lazyOnload"
        onLoad={onInteropLoad}
      />

      <div id={SECTION_ID} className="mb-8">
        <SectionHeader
          title={['Ranking del mercado', 'inmobiliario en El Salvador']}
          subtitle="Top de departamentos según precio mediano y nivel de oferta inmobiliaria."
        />

        {/* Live indicator */}
        {status === 'ready' && (
          <div className="ranking-charts-live-bar">
            <span className="ranking-charts-live-dot" />
            <span className="ranking-charts-live-text">Live</span>
            <span className="ranking-charts-live-ago">
              Actualizado hace {secondsAgo < 5 ? 'un momento' : `${secondsAgo}s`}
            </span>
          </div>
        )}

        {/* Loading skeleton */}
        {(status === 'idle' || status === 'loading') && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {[0, 1, 2].map((i) => (
              <div key={i} className="ranking-chart-skeleton">
                <div className="skeleton-title" />
                <div className="skeleton-subtitle" />
                <div className="skeleton-bars">
                  <div className="skeleton-bar" style={{ width: '90%' }} />
                  <div className="skeleton-bar" style={{ width: '65%' }} />
                  <div className="skeleton-bar" style={{ width: '45%' }} />
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Error state */}
        {status === 'error' && (
          <div className="card-float p-8 text-center">
            <p className="text-[var(--text-secondary)] mb-4">No se pudieron cargar los gráficos.</p>
            <button onClick={handleRetry} className="btn-primary">
              Reintentar
            </button>
          </div>
        )}

        {/* Empty state */}
        {status === 'empty' && (
          <div className="card-float p-8 text-center">
            <p className="text-[var(--text-secondary)]">Sin datos disponibles.</p>
          </div>
        )}

        {/* Chart containers — always in DOM for ECharts to mount into */}
        <div
          className="grid grid-cols-1 md:grid-cols-3 gap-5"
          style={{ display: status === 'ready' ? 'grid' : 'none' }}
        >
          <div className="ranking-chart-card">
            <div id="chart-expensive" className="ranking-chart-canvas" />
          </div>
          <div className="ranking-chart-card">
            <div id="chart-cheap" className="ranking-chart-canvas" />
          </div>
          <div className="ranking-chart-card">
            <div id="chart-active" className="ranking-chart-canvas" />
          </div>
        </div>
      </div>
    </>
  );
}
