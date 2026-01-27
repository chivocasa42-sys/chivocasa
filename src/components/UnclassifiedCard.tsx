'use client';

interface UnclassifiedCardProps {
    count: number;
    onClick: () => void;
}

export default function UnclassifiedCard({ count, onClick }: UnclassifiedCardProps) {
    if (count === 0) return null;

    return (
        <div
            className="col-span-full bg-amber-50 rounded-lg px-5 py-3 border-l-4 border-amber-400 flex items-center justify-between cursor-pointer hover:bg-amber-100 transition-colors"
            onClick={onClick}
        >
            <div className="flex items-center gap-3">
                <span className="text-amber-600">⚠️</span>
                <span className="font-medium text-amber-800">NO CLASIFICADO</span>
                <span className="bg-amber-200 text-amber-800 text-xs font-bold px-2 py-0.5 rounded-full">
                    {count}
                </span>
                <span className="text-amber-700 text-sm">
                    • Listings sin ubicación detectada
                </span>
            </div>
            <div className="text-amber-600 text-sm font-medium flex items-center gap-1">
                Ver detalles
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 16 16">
                    <path fillRule="evenodd" d="M4.646 1.646a.5.5 0 0 1 .708 0l6 6a.5.5 0 0 1 0 .708l-6 6a.5.5 0 0 1-.708-.708L10.293 8 4.646 2.354a.5.5 0 0 1 0-.708z" />
                </svg>
            </div>
        </div>
    );
}
