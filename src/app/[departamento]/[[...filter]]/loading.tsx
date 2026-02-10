export default function Loading() {
    // Render 8 skeleton cards matching the ListingCard layout
    const skeletonCards = Array.from({ length: 8 });

    return (
        <main className="container mx-auto px-4 max-w-7xl">
            <div className="mb-8">
                {/* Back link skeleton */}
                <div className="skeleton-pulse mb-5" style={{ height: 20, width: 140 }} />

                <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
                    <div>
                        {/* Title skeleton */}
                        <div className="skeleton-pulse mb-3" style={{ height: 48, width: 280 }} />
                        {/* Status line skeleton */}
                        <div className="skeleton-pulse" style={{ height: 18, width: 200 }} />
                    </div>
                    <div className="flex flex-wrap items-center gap-4">
                        {/* Filter pills skeleton */}
                        <div className="flex gap-2">
                            <div className="skeleton-pulse" style={{ height: 38, width: 72, borderRadius: 999 }} />
                            <div className="skeleton-pulse" style={{ height: 38, width: 72, borderRadius: 999 }} />
                            <div className="skeleton-pulse" style={{ height: 38, width: 72, borderRadius: 999 }} />
                        </div>
                        {/* Sort dropdown skeleton */}
                        <div className="skeleton-pulse" style={{ height: 38, width: 180, borderRadius: 8 }} />
                    </div>
                </div>
            </div>

            {/* Best Opportunity skeleton */}
            <div className="skeleton-pulse skeleton-opportunity" />

            {/* Filter bar skeleton */}
            <div className="skeleton-pulse skeleton-filter-bar" />

            {/* Section header skeleton */}
            <div className="text-center mb-6 pb-4 border-b border-slate-200">
                <div className="skeleton-pulse mx-auto mb-2" style={{ height: 32, width: 260 }} />
                <div className="skeleton-pulse mx-auto" style={{ height: 18, width: 320 }} />
            </div>

            {/* Listing cards skeleton grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5 mb-8">
                {skeletonCards.map((_, i) => (
                    <div key={i} className="skeleton-card">
                        <div className="skeleton-pulse skeleton-card__image" />
                        <div className="skeleton-card__body">
                            <div className="skeleton-pulse skeleton-card__price" />
                            <div className="skeleton-pulse skeleton-card__specs" />
                            <div className="skeleton-card__tags">
                                <div className="skeleton-pulse skeleton-card__tag" />
                                <div className="skeleton-pulse skeleton-card__tag" />
                            </div>
                        </div>
                    </div>
                ))}
            </div>
        </main>
    );
}
