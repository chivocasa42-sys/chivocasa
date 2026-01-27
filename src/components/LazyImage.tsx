'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { imageCache } from '@/lib/imageCache';

interface LazyImageProps {
    src: string;
    alt: string;
    className?: string;
    placeholderSrc?: string;
    onError?: () => void;
}

export default function LazyImage({
    src,
    alt,
    className = '',
    placeholderSrc = 'https://via.placeholder.com/400x200?text=Sin+Imagen',
    onError,
}: LazyImageProps) {
    const [imageSrc, setImageSrc] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [hasError, setHasError] = useState(false);
    const [isInView, setIsInView] = useState(false);
    const imgRef = useRef<HTMLDivElement>(null);

    // Intersection Observer for lazy loading
    useEffect(() => {
        const element = imgRef.current;
        if (!element) return;

        const observer = new IntersectionObserver(
            (entries) => {
                entries.forEach((entry) => {
                    if (entry.isIntersecting) {
                        setIsInView(true);
                        observer.disconnect();
                    }
                });
            },
            {
                rootMargin: '100px', // Start loading 100px before entering viewport
                threshold: 0.01,
            }
        );

        observer.observe(element);

        return () => {
            observer.disconnect();
        };
    }, []);

    // Load image when in view
    useEffect(() => {
        if (!isInView || !src) return;

        // Check if already cached
        const cachedUrl = imageCache.getCachedUrl(src);
        if (cachedUrl) {
            setImageSrc(cachedUrl);
            setIsLoading(false);
            return;
        }

        // Load through cache manager
        imageCache
            .getImage(src)
            .then((objectUrl) => {
                if (objectUrl) {
                    setImageSrc(objectUrl);
                } else {
                    setHasError(true);
                    onError?.();
                }
                setIsLoading(false);
            })
            .catch(() => {
                setHasError(true);
                setIsLoading(false);
                onError?.();
            });
    }, [isInView, src, onError]);

    const handleNativeError = useCallback(() => {
        setHasError(true);
        setIsLoading(false);
        onError?.();
    }, [onError]);

    return (
        <div ref={imgRef} className={`relative overflow-hidden ${className}`}>
            {/* Loading skeleton */}
            {isLoading && (
                <div className="absolute inset-0 bg-gradient-to-r from-slate-200 via-slate-100 to-slate-200 animate-pulse" />
            )}

            {/* Actual image */}
            {(imageSrc || hasError) && (
                <img
                    src={hasError ? placeholderSrc : imageSrc || placeholderSrc}
                    alt={alt}
                    className={`w-full h-full object-cover transition-opacity duration-300 ${isLoading ? 'opacity-0' : 'opacity-100'
                        }`}
                    loading="lazy"
                    decoding="async"
                    onError={handleNativeError}
                    onLoad={() => setIsLoading(false)}
                />
            )}

            {/* Placeholder while loading */}
            {!imageSrc && !hasError && !isLoading && isInView && (
                <img
                    src={placeholderSrc}
                    alt={alt}
                    className="w-full h-full object-cover"
                    loading="lazy"
                />
            )}
        </div>
    );
}
