// Funciones de cálculo para métricas BI
import { Listing } from '@/types/listing';
import {
    NationalStats,
    DepartmentBIStats,
    Insights,
    InsightItem,
    MunicipioStats,
    HomeBIData
} from '@/types/biStats';
import { DEPARTAMENTOS, detectDepartamento } from '@/data/departamentos';

// Calcular percentil de un array de números
export function calculatePercentile(values: number[], percentile: number): number {
    if (values.length === 0) return 0;
    const filtered = values.filter(v => v > 0);
    if (filtered.length === 0) return 0;

    const sorted = [...filtered].sort((a, b) => a - b);
    const index = (percentile / 100) * (sorted.length - 1);
    const lower = Math.floor(index);
    const upper = Math.ceil(index);

    if (lower === upper) return sorted[lower];
    return Math.round(sorted[lower] * (upper - index) + sorted[upper] * (index - lower));
}

// Verificar si una fecha está dentro de los últimos N días
export function isWithinDays(dateStr: string | undefined, days: number): boolean {
    if (!dateStr) return false;
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffDays = diffMs / (1000 * 60 * 60 * 24);
    return diffDays <= days;
}

// Extraer ubicación de un listing
function getLocationString(listing: Listing): string {
    const loc = listing.location;
    if (loc) {
        if (typeof loc === 'string' && loc.trim()) return loc.trim();
        if (typeof loc === 'object' && loc !== null) {
            const locObj = loc as Record<string, unknown>;
            const name = locObj.municipio_detectado || locObj.name || locObj.city || locObj.zona || locObj.area;
            if (name) return String(name);
        }
    }
    return listing.title || '';
}

// Calcular estadísticas nacionales
export function calculateNationalStats(listings: Listing[]): NationalStats {
    const saleListings = listings.filter(l => l.listing_type === 'sale');
    const rentListings = listings.filter(l => l.listing_type === 'rent');

    const salePrices = saleListings.map(l => l.price).filter(p => p > 0);
    const rentPrices = rentListings.map(l => l.price).filter(p => p > 0);

    // Calcular nuevos últimos 7 días vs 7-14 días
    const new_7d = listings.filter(l => isWithinDays(l.scraped_at || l.last_updated, 7)).length;
    const new_prev_7d = listings.filter(l => {
        const dateStr = l.scraped_at || l.last_updated;
        if (!dateStr) return false;
        const date = new Date(dateStr);
        const now = new Date();
        const diffDays = (now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24);
        return diffDays > 7 && diffDays <= 14;
    }).length;

    return {
        median_sale: calculatePercentile(salePrices, 50),
        median_rent: calculatePercentile(rentPrices, 50),
        total_active: listings.length,
        new_7d,
        new_prev_7d,
        updated_at: new Date().toISOString(),
        sources: ['Encuentra24', 'MiCasaSV', 'Realtor']
    };
}


// Calcular estadísticas por departamento
export function calculateDepartmentBIStats(
    listings: Listing[],
    filterType: 'all' | 'sale' | 'rent'
): { departments: DepartmentBIStats[]; unclassified: { count: number; listings: Listing[] } } {

    // Filtrar por tipo
    let filtered = listings;
    if (filterType === 'sale') {
        filtered = listings.filter(l => l.listing_type === 'sale');
    } else if (filterType === 'rent') {
        filtered = listings.filter(l => l.listing_type === 'rent');
    }

    // Agrupar por departamento y municipio
    const deptGroups: Record<string, {
        listings: Listing[];
        municipios: Record<string, Listing[]>
    }> = {};

    // Inicializar departamentos
    for (const dept of Object.keys(DEPARTAMENTOS)) {
        deptGroups[dept] = { listings: [], municipios: {} };
    }

    const unclassifiedListings: Listing[] = [];

    // Clasificar cada listing
    filtered.forEach(listing => {
        const locationStr = getLocationString(listing);
        const detected = detectDepartamento(locationStr);

        if (detected) {
            const { departamento, municipio } = detected;
            if (!deptGroups[departamento]) {
                deptGroups[departamento] = { listings: [], municipios: {} };
            }
            deptGroups[departamento].listings.push(listing);

            if (!deptGroups[departamento].municipios[municipio]) {
                deptGroups[departamento].municipios[municipio] = [];
            }
            deptGroups[departamento].municipios[municipio].push(listing);
        } else {
            unclassifiedListings.push(listing);
        }
    });

    // Calcular estadísticas por departamento
    const departments: DepartmentBIStats[] = [];

    for (const [dept, data] of Object.entries(deptGroups)) {
        if (data.listings.length === 0) continue;

        const prices = data.listings.map(l => l.price).filter(p => p > 0);
        const new7d = data.listings.filter(l =>
            isWithinDays(l.scraped_at || l.last_updated, 7)
        ).length;

        // Calcular municipios stats
        const municipiosStats: Record<string, MunicipioStats> = {};
        for (const [muni, muniListings] of Object.entries(data.municipios)) {
            const muniPrices = muniListings.map(l => l.price).filter(p => p > 0);
            municipiosStats[muni] = {
                count: muniListings.length,
                median_price: calculatePercentile(muniPrices, 50),
                p25_price: calculatePercentile(muniPrices, 25),
                p75_price: calculatePercentile(muniPrices, 75),
                new_7d: muniListings.filter(l => isWithinDays(l.scraped_at || l.last_updated, 7)).length,
                listings: muniListings
            };
        }

        departments.push({
            departamento: dept,
            count_active: data.listings.length,
            municipios_con_actividad: Object.keys(data.municipios).length,
            median_price: calculatePercentile(prices, 50),
            p25_price: calculatePercentile(prices, 25),
            p75_price: calculatePercentile(prices, 75),
            new_7d: new7d,
            trend_30d_pct: 0, // Se calculará si hay data histórica
            municipios: municipiosStats
        });
    }

    // Ordenar por count descendente
    departments.sort((a, b) => b.count_active - a.count_active);

    return {
        departments,
        unclassified: {
            count: unclassifiedListings.length,
            listings: unclassifiedListings
        }
    };
}

// Calcular insights (top 3 subidas, bajadas, actividad)
export function calculateInsights(departments: DepartmentBIStats[]): Insights {
    // Recopilar todos los municipios con sus stats
    const allMunicipios: Array<{
        municipio: string;
        departamento: string;
        new_7d: number;
        trend_30d_pct: number;
    }> = [];

    for (const dept of departments) {
        for (const [muni, stats] of Object.entries(dept.municipios)) {
            if (stats.count >= 3) { // Solo municipios con suficiente data
                allMunicipios.push({
                    municipio: muni,
                    departamento: dept.departamento,
                    new_7d: stats.new_7d,
                    trend_30d_pct: 0 // Placeholder - requiere data histórica
                });
            }
        }
    }

    // Top 3 más activos (7 días)
    const top3_active_7d: InsightItem[] = [...allMunicipios]
        .sort((a, b) => b.new_7d - a.new_7d)
        .slice(0, 3)
        .map(m => ({
            municipio: m.municipio,
            departamento: m.departamento,
            value: m.new_7d
        }));

    // Para trends necesitaríamos data histórica - por ahora placeholder
    const top3_up_30d: InsightItem[] = [];
    const top3_down_30d: InsightItem[] = [];

    return {
        top3_up_30d,
        top3_down_30d,
        top3_active_7d
    };
}

// Función principal que calcula todo
export function calculateHomeBIData(
    listings: Listing[],
    filterType: 'all' | 'sale' | 'rent'
): HomeBIData {
    const national = calculateNationalStats(listings);
    const { departments, unclassified } = calculateDepartmentBIStats(listings, filterType);
    const insights = calculateInsights(departments);

    return {
        national,
        departments,
        insights,
        unclassified
    };
}

// Formatear precio
export function formatPrice(price: number): string {
    if (!price || price === 0) return 'N/A';
    return '$' + price.toLocaleString('en-US');
}

// Formatear porcentaje con flecha
export function formatTrend(pct: number): { text: string; direction: 'up' | 'down' | 'neutral' } {
    if (pct > 0) {
        return { text: `+${pct.toFixed(1)}%`, direction: 'up' };
    } else if (pct < 0) {
        return { text: `${pct.toFixed(1)}%`, direction: 'down' };
    }
    return { text: '0%', direction: 'neutral' };
}

// Formatear hora
export function formatTime(isoString: string): string {
    const date = new Date(isoString);
    return date.toLocaleTimeString('es-SV', {
        hour: 'numeric',
        minute: '2-digit',
        hour12: true
    });
}
