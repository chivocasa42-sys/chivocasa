'use client';

import { useState, useEffect, useCallback } from 'react';
import Navbar from '@/components/Navbar';
import LocationCard from '@/components/LocationCard';
import ListingsView from '@/components/ListingsView';
import { Listing, LocationStats } from '@/types/listing';

type FilterType = 'all' | 'sale' | 'rent';

// Helper to extract location string from listing data
function getLocationString(listing: Listing): string {
  // Try location field first
  const loc = listing.location;
  if (loc) {
    if (typeof loc === 'string' && loc.trim()) return loc.trim();
    if (typeof loc === 'object' && loc !== null) {
      const locObj = loc as Record<string, unknown>;
      const name = locObj.name || locObj.city || locObj.zona || locObj.area;
      if (name) return String(name);
    }
  }

  // Try details.Ubicación or details.Localización
  const details = listing.details || {};
  if (details['Ubicación']) return details['Ubicación'];
  if (details['Localización']) return details['Localización'];

  // Try extracting from title (format: "Venta/Alquiler de Casas en [Location]")
  const title = listing.title || '';
  const locationMatch = title.match(/(?:en|in)\s+([A-Za-zÀ-ÿ\s]+?)(?:\s*[|\-]|$)/i);
  if (locationMatch && locationMatch[1]) {
    return locationMatch[1].trim();
  }

  // Try extracting from "Dirección exacta" detail
  if (details['Dirección exacta']) {
    const addr = details['Dirección exacta'];
    // Extract last part (often city/zone)
    const parts = addr.split(',').map(p => p.trim());
    if (parts.length > 0) {
      return parts[parts.length - 1] || parts[0];
    }
  }

  return 'Otros';
}

function calculateStats(listings: Listing[]): Record<string, LocationStats> {
  const groups: Record<string, Listing[]> = {};

  listings.forEach((l) => {
    const loc = getLocationString(l);
    if (!groups[loc]) groups[loc] = [];
    groups[loc].push(l);
  });

  const stats: Record<string, LocationStats> = {};
  for (const [loc, items] of Object.entries(groups)) {
    const prices = items.filter((i) => i.price && i.price > 0).map((i) => i.price);
    stats[loc] = {
      count: items.length,
      listings: items,
      avg: prices.length ? Math.round(prices.reduce((a, b) => a + b, 0) / prices.length) : 0,
      min: prices.length ? Math.min(...prices) : 0,
      max: prices.length ? Math.max(...prices) : 0,
    };
  }
  return stats;
}

export default function Home() {
  const [allListings, setAllListings] = useState<Listing[]>([]);
  const [locationStats, setLocationStats] = useState<Record<string, LocationStats>>({});
  const [currentFilter, setCurrentFilter] = useState<FilterType>('all');
  const [currentLocation, setCurrentLocation] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchListings = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/listings');
      if (!res.ok) throw new Error('Failed to fetch');
      const data = await res.json();
      setAllListings(data);
    } catch (err) {
      setError('Error loading data');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchListings();
  }, [fetchListings]);

  useEffect(() => {
    let filtered = allListings;
    if (currentFilter === 'sale') {
      filtered = allListings.filter((l) => l.listing_type === 'sale');
    } else if (currentFilter === 'rent') {
      filtered = allListings.filter((l) => l.listing_type === 'rent');
    }
    setLocationStats(calculateStats(filtered));
  }, [allListings, currentFilter]);

  const sortedLocations = Object.entries(locationStats).sort((a, b) => a[1].avg - b[1].avg);

  const filteredCount = currentFilter === 'all'
    ? allListings.length
    : allListings.filter((l) => l.listing_type === currentFilter).length;

  if (currentLocation && locationStats[currentLocation]) {
    return (
      <>
        <Navbar totalListings={filteredCount} onRefresh={fetchListings} />
        <div className="container mx-auto px-4">
          <ListingsView
            location={currentLocation}
            stats={locationStats[currentLocation]}
            allListings={allListings}
            onBack={() => setCurrentLocation(null)}
          />
        </div>
      </>
    );
  }

  return (
    <>
      <Navbar totalListings={filteredCount} onRefresh={fetchListings} />
      <div className="container mx-auto px-4">
        {/* Header with filters */}
        <div className="flex flex-wrap justify-between items-center gap-3 mb-6">
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <svg className="w-6 h-6 text-[var(--accent)]" fill="currentColor" viewBox="0 0 16 16">
              <path d="M8 16s6-5.686 6-10A6 6 0 0 0 2 6c0 4.314 6 10 6 10zm0-7a3 3 0 1 1 0-6 3 3 0 0 1 0 6z" />
            </svg>
            Ubicaciones
          </h2>
          <div className="flex">
            <button
              onClick={() => setCurrentFilter('all')}
              className={`filter-btn ${currentFilter === 'all' ? 'active' : ''}`}
            >
              Todos
            </button>
            <button
              onClick={() => setCurrentFilter('sale')}
              className={`filter-btn ${currentFilter === 'sale' ? 'active' : ''}`}
            >
              Venta
            </button>
            <button
              onClick={() => setCurrentFilter('rent')}
              className={`filter-btn ${currentFilter === 'rent' ? 'active' : ''}`}
            >
              Alquiler
            </button>
          </div>
        </div>

        {/* Content */}
        {isLoading ? (
          <div className="flex justify-center items-center min-h-[300px]">
            <div className="spinner"></div>
          </div>
        ) : error ? (
          <div className="text-center text-red-500 py-12">
            <svg className="w-12 h-12 mx-auto mb-4" fill="currentColor" viewBox="0 0 16 16">
              <path d="M7.938 2.016A.13.13 0 0 1 8.002 2a.13.13 0 0 1 .063.016.146.146 0 0 1 .054.057l6.857 11.667c.036.06.035.124.002.183a.163.163 0 0 1-.054.06.116.116 0 0 1-.066.017H1.146a.115.115 0 0 1-.066-.017.163.163 0 0 1-.054-.06.176.176 0 0 1 .002-.183L7.884 2.073a.147.147 0 0 1 .054-.057zm1.044-.45a1.13 1.13 0 0 0-1.96 0L.165 13.233c-.457.778.091 1.767.98 1.767h13.713c.889 0 1.438-.99.98-1.767L8.982 1.566z" />
              <path d="M7.002 12a1 1 0 1 1 2 0 1 1 0 0 1-2 0zM7.1 5.995a.905.905 0 1 1 1.8 0l-.35 3.507a.552.552 0 0 1-1.1 0L7.1 5.995z" />
            </svg>
            <p>{error}</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {sortedLocations.map(([loc, stats]) => (
              <LocationCard
                key={loc}
                location={loc}
                stats={stats}
                onClick={() => setCurrentLocation(loc)}
              />
            ))}
          </div>
        )}
      </div>
    </>
  );
}
