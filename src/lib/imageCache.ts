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

interface QueueItem {
    url: string;
    resolve: (objectUrl: string | null) => void;
    reject: (error: Error) => void;
}

class ImageCacheManager {
    private cache: Map<string, CacheEntry> = new Map();
    private queue: QueueItem[] = [];
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
            } else if (cached.status === 'loading' || cached.status === 'pending') {
                // Already loading, wait for it
                return new Promise((resolve, reject) => {
                    this.queue.push({ url, resolve, reject });
                });
            } else if (cached.status === 'error') {
                // Previous error, retry
                this.cache.delete(url);
            }
        }

        // Add to queue and start processing
        return new Promise((resolve, reject) => {
            this.cache.set(url, {
                url,
                blob: null,
                objectUrl: null,
                status: 'pending',
                timestamp: Date.now(),
            });
            this.queue.push({ url, resolve, reject });
            this.processQueue();
        });
    }

    private async processQueue() {
        while (this.queue.length > 0 && this.activeRequests < this.maxConcurrentRequests) {
            const item = this.queue.shift();
            if (!item) continue;

            const cached = this.cache.get(item.url);
            if (!cached) {
                item.resolve(null);
                continue;
            }

            // If already loaded by another request, resolve immediately
            if (cached.status === 'loaded' && cached.objectUrl) {
                item.resolve(cached.objectUrl);
                continue;
            }

            // Skip if already being fetched
            if (cached.status === 'loading') {
                this.queue.push(item);
                continue;
            }

            this.activeRequests++;
            cached.status = 'loading';

            try {
                const response = await fetch(item.url, {
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

                item.resolve(objectUrl);

                // Resolve all pending requests for same URL
                this.resolvePending(item.url, objectUrl);
            } catch (error) {
                cached.status = 'error';
                cached.error = error instanceof Error ? error.message : 'Unknown error';
                item.reject(error instanceof Error ? error : new Error('Failed to fetch image'));

                // Reject all pending requests for same URL
                this.rejectPending(item.url, error instanceof Error ? error : new Error('Failed to fetch'));
            } finally {
                this.activeRequests--;
                this.processQueue();
            }
        }
    }

    private resolvePending(url: string, objectUrl: string) {
        const pending = this.queue.filter((item) => item.url === url);
        pending.forEach((item) => item.resolve(objectUrl));
        this.queue = this.queue.filter((item) => item.url !== url);
    }

    private rejectPending(url: string, error: Error) {
        const pending = this.queue.filter((item) => item.url === url);
        pending.forEach((item) => item.reject(error));
        this.queue = this.queue.filter((item) => item.url !== url);
    }

    private evictOldest() {
        let oldest: CacheEntry | null = null;
        let oldestKey: string | null = null;

        this.cache.forEach((entry, key) => {
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
    }
}

// Singleton instance
export const imageCache = new ImageCacheManager();
