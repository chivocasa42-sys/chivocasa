'use client';

import { LocationStats } from '@/types/listing';

interface DepartmentCardProps {
    departamento: string;
    stats: LocationStats;
    municipiosCount: number;
    onClick: () => void;
}

function formatPrice(price: number): string {
    if (!price) return 'N/A';
    return '$' + price.toLocaleString('en-US');
}

export default function DepartmentCard({ departamento, stats, municipiosCount, onClick }: DepartmentCardProps) {
    return (
        <div
            className="card card-location h-full flex flex-col cursor-pointer hover:scale-[1.02] transition-transform"
            onClick={onClick}
        >
            <div className="p-4 flex-1">
                <div className="flex justify-between items-start mb-3">
                    <h5 className="font-semibold text-lg flex items-center gap-2">
                        <svg className="w-5 h-5 text-[var(--accent)]" fill="currentColor" viewBox="0 0 16 16">
                            <path d="M8 16s6-5.686 6-10A6 6 0 0 0 2 6c0 4.314 6 10 6 10zm0-7a3 3 0 1 1 0-6 3 3 0 0 1 0 6z" />
                        </svg>
                        {departamento}
                    </h5>
                    <span className="badge-count">{stats.count}</span>
                </div>

                <div className="text-sm text-gray-500 mb-2">
                    {municipiosCount} {municipiosCount === 1 ? 'municipio' : 'municipios'} con propiedades
                </div>

                <div className="price-avg mb-2">{formatPrice(stats.avg)}</div>
                <div className="price-range flex items-center gap-1 text-sm">
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
                <small className="text-muted flex items-center justify-end gap-1">
                    Ver municipios
                    <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 16 16">
                        <path fillRule="evenodd" d="M4.646 1.646a.5.5 0 0 1 .708 0l6 6a.5.5 0 0 1 0 .708l-6 6a.5.5 0 0 1-.708-.708L10.293 8 4.646 2.354a.5.5 0 0 1 0-.708z" />
                    </svg>
                </small>
            </div>
        </div>
    );
}
