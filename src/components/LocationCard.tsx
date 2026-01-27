'use client';

import { LocationStats } from '@/types/listing';

interface LocationCardProps {
    location: string;
    stats: LocationStats;
    onClick: () => void;
}

function formatPrice(price: number): string {
    if (!price) return 'N/A';
    return '$' + price.toLocaleString('en-US');
}

export default function LocationCard({ location, stats, onClick }: LocationCardProps) {
    return (
        <div
            className="card card-location h-full flex flex-col"
            onClick={onClick}
        >
            <div className="p-4 flex-1">
                <div className="flex justify-between items-start mb-3">
                    <h5 className="font-semibold text-lg flex items-center gap-1">
                        <svg className="w-4 h-4 text-[var(--accent)]" fill="currentColor" viewBox="0 0 16 16">
                            <path d="M8 16s6-5.686 6-10A6 6 0 0 0 2 6c0 4.314 6 10 6 10zm0-7a3 3 0 1 1 0-6 3 3 0 0 1 0 6z" />
                        </svg>
                        {location}
                    </h5>
                    <span className="badge-count">{stats.count}</span>
                </div>
                <div className="price-avg mb-2">{formatPrice(stats.avg)}</div>
                <div className="price-range flex items-center gap-1">
                    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 16 16">
                        <path fillRule="evenodd" d="M8 4a.5.5 0 0 1 .5.5v5.793l2.146-2.147a.5.5 0 0 1 .708.708l-3 3a.5.5 0 0 1-.708 0l-3-3a.5.5 0 1 1 .708-.708L7.5 10.293V4.5A.5.5 0 0 1 8 4z" />
                    </svg>
                    {formatPrice(stats.min)}
                    <span className="mx-2">—</span>
                    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 16 16">
                        <path fillRule="evenodd" d="M8 12a.5.5 0 0 0 .5-.5V5.707l2.146 2.147a.5.5 0 0 0 .708-.708l-3-3a.5.5 0 0 0-.708 0l-3 3a.5.5 0 1 0 .708.708L7.5 5.707V11.5a.5.5 0 0 0 .5.5z" />
                    </svg>
                    {formatPrice(stats.max)}
                </div>
            </div>
            <div className="px-4 py-3 border-t border-gray-200 text-right bg-transparent">
                <small className="text-muted">
                    View listings
                    <svg className="w-3 h-3 inline ml-1" fill="currentColor" viewBox="0 0 16 16">
                        <path fillRule="evenodd" d="M4.646 1.646a.5.5 0 0 1 .708 0l6 6a.5.5 0 0 1 0 .708l-6 6a.5.5 0 0 1-.708-.708L10.293 8 4.646 2.354a.5.5 0 0 1 0-.708z" />
                    </svg>
                </small>
            </div>
        </div>
    );
}
