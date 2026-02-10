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
  type ViewType,
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
  activeFilter?: ViewType;
}

const REFRESH_INTERVAL_MS = 30_000;
const SECTION_ID = 'market-ranking-charts-section';
const CACHE_KEY = 'mrc_ranking_cache';

// localStorage helpers
function readCache(): DepartmentStats[] | null {
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { data: DepartmentStats[]; ts: number };
    if (Date.now() - parsed.ts > 300_000) return null;
    return parsed.data;
  } catch {
    return null;
  }
}

function writeCache(data: DepartmentStats[]) {
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify({ data, ts: Date.now() }));
  } catch { /* quota exceeded — ignore */ }
}

// Detect if scripts are already loaded globally (SPA return navigation)
function scriptsAlreadyLoaded(): boolean {
  return typeof window !== 'undefined' &&
    typeof window.echarts !== 'undefined' &&
    !!window.MarketRankingCharts;
}

// Pill config per filter — reuses same classes as DepartmentCard
const PILL_CONFIG: Record<ViewType, { label: string; pillClass: string; labelClass: string }> = {
  all:  { label: 'TOTAL', pillClass: 'dept-card__pill--todos',  labelClass: 'dept-card__pill-label--todos' },
  sale: { label: 'VENTA', pillClass: '',                        labelClass: 'dept-card__pill-label--venta' },
  rent: { label: 'RENTA', pillClass: 'dept-card__pill--renta',  labelClass: 'dept-card__pill-label--renta' },
};

export default function MarketRankingCharts({ departments, activeFilter = 'all' }: MarketRankingChartsProps) {
  const router = useRouter();
  const [status, setStatus] = useState<'idle' | 'loading' | 'ready' | 'error' | 'empty'>('idle');
  const [pulsing, setPulsing] = useState(false);

  const chartsInitialized = useRef(false);
  const isVisible = useRef(false);
  const pollingTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const echartsLoaded = useRef(scriptsAlreadyLoaded());
  const interopLoaded = useRef(scriptsAlreadyLoaded());
  const initialDataRendered = useRef(false);
  const fetchInFlight = useRef(false);

  // Navigate on bar click
  const handleBarClick = useCallback((slug: string) => {
    router.push(`/${slug}`);
  }, [router]);

  // Micro-pulse on the LIVE dot when fresh data arrives
  const triggerPulse = useCallback(() => {
    setPulsing(true);
    setTimeout(() => setPulsing(false), 400);
  }, []);

  // Render charts with current data
  const renderCharts = useCallback((depts: DepartmentStats[], shouldCache = true) => {
    if (!window.MarketRankingCharts || !window.MarketRankingCharts.isReady()) return false;

    const { topExpensive, topCheap, topActive } = computeRankings(depts, activeFilter);

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
        triggerPulse();
        if (shouldCache) writeCache(depts);
        return true;
      }
      return false;
    } else {
      window.MarketRankingCharts.updateAllCharts(expData, cheapData, activeData);
      triggerPulse();
      if (shouldCache) writeCache(depts);
      return true;
    }
  }, [handleBarClick, triggerPulse]);

  // Fetch fresh data from API (with concurrency lock)
  const fetchAndUpdate = useCallback(async () => {
    if (fetchInFlight.current) return;
    fetchInFlight.current = true;
    try {
      const res = await fetch('/api/department-stats');
      if (!res.ok) throw new Error('Failed to fetch');
      const data: DepartmentStats[] = await res.json();
      renderCharts(data);
    } catch {
      if (!chartsInitialized.current) {
        setStatus('error');
      }
    } finally {
      fetchInFlight.current = false;
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
    // Re-check global availability (covers SPA return where onLoad doesn't re-fire)
    if (scriptsAlreadyLoaded()) {
      echartsLoaded.current = true;
      interopLoaded.current = true;
    }

    if (!echartsLoaded.current || !interopLoaded.current) return;
    if (!isVisible.current) return;
    if (initialDataRendered.current) return;

    // 1) Try localStorage cache for instant render (warm-start)
    const cached = readCache();
    if (cached && cached.length > 0) {
      const ok = renderCharts(cached, false);
      if (ok) {
        initialDataRendered.current = true;
        fetchAndUpdate();
        startPolling();
        return;
      }
    }

    // 2) Try prop data
    if (departments.length > 0) {
      setStatus('loading');
      const ok = renderCharts(departments);
      if (ok) {
        initialDataRendered.current = true;
        startPolling();
        return;
      }
    }

    // 3) Fallback: fetch from API
    setStatus('loading');
    fetchAndUpdate().then(() => {
      initialDataRendered.current = true;
      startPolling();
    });
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

  // Setup IntersectionObserver after mount (with rootMargin + immediate check)
  useEffect(() => {
    const el = document.getElementById(SECTION_ID);
    if (!el) return;

    const handleVisible = () => {
      if (!isVisible.current) {
        isVisible.current = true;
        tryInit();
        startPolling();
      }
    };

    const handleHidden = () => {
      isVisible.current = false;
      stopPolling();
    };

    const obs = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            handleVisible();
          } else {
            handleHidden();
          }
        });
      },
      { threshold: 0.3, rootMargin: '300px 0px 300px 0px' }
    );

    obs.observe(el);

    // Immediate check: if already in viewport, don't wait for scroll
    const rect = el.getBoundingClientRect();
    const inViewport = rect.top < window.innerHeight + 300 && rect.bottom > -300;
    if (inViewport) {
      handleVisible();
    }

    return () => {
      obs.disconnect();
      stopPolling();
      // Do NOT destroy charts — let getInstanceByDom reuse them on return navigation
    };
  }, [tryInit, startPolling, stopPolling]);

  // Re-render immediately when filter changes (no 30s wait)
  useEffect(() => {
    if (!chartsInitialized.current) return;
    if (departments.length > 0) {
      renderCharts(departments);
    } else {
      const cached = readCache();
      if (cached && cached.length > 0) renderCharts(cached, false);
    }
  }, [activeFilter]); // eslint-disable-line react-hooks/exhaustive-deps

  // Retry handler
  const handleRetry = () => {
    setStatus('loading');
    initialDataRendered.current = false;
    chartsInitialized.current = false;
    tryInit();
  };

  return (
    <>
      {/* Apache ECharts CDN — afterInteractive for faster load + reliable onLoad on SPA */}
      <Script
        src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"
        strategy="afterInteractive"
        onLoad={onEChartsLoad}
      />
      {/* Interop script */}
      <Script
        src="/js/marketRankingCharts.js"
        strategy="afterInteractive"
        onLoad={onInteropLoad}
      />

      <div id={SECTION_ID} className="mb-8">
        <SectionHeader
          title={['Ranking del mercado', 'inmobiliario en El Salvador']}
          subtitle="Top de departamentos según precio mediano y nivel de oferta inmobiliaria."
        />

        {/* Live indicator — simple, no timer */}
        {status === 'ready' && (
          <div className="ranking-charts-live-bar">
            <span className={`ranking-charts-live-dot${pulsing ? ' ranking-charts-live-dot-pulse' : ''}`} />
            <span className="ranking-charts-live-text">LIVE</span>
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
          {['chart-expensive', 'chart-cheap', 'chart-active'].map((id) => {
            const pill = PILL_CONFIG[activeFilter];
            return (
              <div key={id} className="ranking-chart-card">
                {/* Filter pill — same markup/classes as DepartmentCard */}
                <div className="dept-card__badge-pill">
                  <div className={`dept-card__pill ${pill.pillClass}`}>
                    <span className={`dept-card__pill-label ${pill.labelClass}`}>{pill.label}</span>
                  </div>
                </div>
                <div id={id} className="ranking-chart-canvas" />
              </div>
            );
          })}
        </div>
      </div>
    </>
  );
}
