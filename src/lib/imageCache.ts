'use client';

// Image cache and request manager to avoid too many parallel requests

interface CacheEntry {
    url: string;
    blob: Blob | null;
    objectUrl: string | null;
    status: 'pending' | 'loading' | 'loaded' | 'error';
    timestamp: number;
    error?: string;
}

interface PendingRequest {
    resolve: (objectUrl: string | null) => void;
    reject: (error: Error) => void;
}

class ImageCacheManager {
    private cache: Map<string, CacheEntry> = new Map();
    // Queue handles URLs that need to be fetched, not individual requests
    private fetchQueue: string[] = [];
    // Listeners handles all waiting promises for a given URL
    private listeners: Map<string, PendingRequest[]> = new Map();

    private activeRequests = 0;
    private maxConcurrentRequests = 4; // Limit parallel fetches
    private cacheMaxAge = 5 * 60 * 1000; // 5 minutes cache lifetime
    private maxCacheSize = 100; // Max images in cache

    // Get cached image or add to queue
    async getImage(url: string): Promise<string | null> {
        // Check if we have a valid cached entry
        const cached = this.cache.get(url);

        if (cached) {
            // Return cached objectUrl if still valid
            if (cached.status === 'loaded' && cached.objectUrl) {
                if (Date.now() - cached.timestamp < this.cacheMaxAge) {
                    return cached.objectUrl;
                } else {
                    // Cache expired, need to refetch
                    this.revokeEntry(cached);
                    this.cache.delete(url);
                }
            } else if (cached.status === 'error') {
                // Previous error, retry
                this.cache.delete(url);
            }
            // If 'loading' or 'pending', we fall through to add to listeners
        }

        return new Promise((resolve, reject) => {
            // Add to listeners for this URL
            if (!this.listeners.has(url)) {
                this.listeners.set(url, []);
            }
            this.listeners.get(url)!.push({ resolve, reject });

            // If not already loading/pending, add to fetch queue
            if (!cached || cached.status === 'error') {
                // Initialize cache entry
                this.cache.set(url, {
                    url,
                    blob: null,
                    objectUrl: null,
                    status: 'pending',
                    timestamp: Date.now(),
                });

                // Add to fetch queue if not already there
                if (!this.fetchQueue.includes(url)) {
                    this.fetchQueue.push(url);
                }

                this.processQueue();
            }
        });
    }

    private async processQueue() {
        if (this.activeRequests >= this.maxConcurrentRequests || this.fetchQueue.length === 0) {
            return;
        }

        const url = this.fetchQueue.shift();
        if (!url) return;

        const cached = this.cache.get(url);
        if (!cached) {
            // Should not happen, but safe fallback
            this.resolveListeners(url, null);
            this.processQueue();
            return;
        }

        this.activeRequests++;
        cached.status = 'loading';

        try {
            const response = await fetch(url, {
                mode: 'cors',
                credentials: 'omit',
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const blob = await response.blob();
            const objectUrl = URL.createObjectURL(blob);

            // Enforce cache size limit
            if (this.cache.size >= this.maxCacheSize) {
                this.evictOldest();
            }

            cached.blob = blob;
            cached.objectUrl = objectUrl;
            cached.status = 'loaded';
            cached.timestamp = Date.now();

            this.resolveListeners(url, objectUrl);

        } catch (error) {
            cached.status = 'error';
            cached.error = error instanceof Error ? error.message : 'Unknown error';

            this.rejectListeners(url, error instanceof Error ? error : new Error('Failed to fetch image'));
        } finally {
            this.activeRequests--;
            this.processQueue();
        }
    }

    private resolveListeners(url: string, objectUrl: string | null) {
        const listeners = this.listeners.get(url);
        if (listeners) {
            listeners.forEach(l => l.resolve(objectUrl));
            this.listeners.delete(url);
        }
    }

    private rejectListeners(url: string, error: Error) {
        const listeners = this.listeners.get(url);
        if (listeners) {
            listeners.forEach(l => l.reject(error));
            this.listeners.delete(url);
        }
    }

    private evictOldest() {
        let oldest: CacheEntry | null = null;
        let oldestKey: string | null = null;

        this.cache.forEach((entry, key) => {
            // Don't evict currently loading images
            if (entry.status === 'loading') return;

            if (!oldest || entry.timestamp < oldest.timestamp) {
                oldest = entry;
                oldestKey = key;
            }
        });

        if (oldestKey && oldest) {
            this.revokeEntry(oldest);
            this.cache.delete(oldestKey);
        }
    }

    private revokeEntry(entry: CacheEntry) {
        if (entry.objectUrl) {
            try {
                URL.revokeObjectURL(entry.objectUrl);
            } catch {
                // Ignore revoke errors
            }
        }
    }

    // Preload images (for visible viewport)
    preloadImages(urls: string[]) {
        urls.forEach((url) => {
            if (!this.cache.has(url)) {
                this.getImage(url).catch(() => {
                    // Silently handle preload failures
                });
            }
        });
    }

    // Check if URL is cached
    isCached(url: string): boolean {
        const entry = this.cache.get(url);
        return entry?.status === 'loaded' && !!entry.objectUrl;
    }

    // Get cached URL synchronously (for immediate display)
    getCachedUrl(url: string): string | null {
        const entry = this.cache.get(url);
        if (entry?.status === 'loaded' && entry.objectUrl) {
            return entry.objectUrl;
        }
        return null;
    }

    // Clear all cache
    clearCache() {
        this.cache.forEach((entry) => this.revokeEntry(entry));
        this.cache.clear();
        this.listeners.clear();
        this.fetchQueue = [];
    }
}

// Singleton instance
export const imageCache = new ImageCacheManager();
