// Tipos para estadísticas BI del Home

export interface NationalStats {
    median_sale: number;
    median_rent: number;
    total_active: number;
    new_7d: number;
    new_prev_7d: number;
    updated_at: string;
    sources: string[];
}


export interface DepartmentBIStats {
    departamento: string;
    count_active: number;
    municipios_con_actividad: number;
    median_price: number;
    p25_price: number;
    p75_price: number;
    new_7d: number;
    trend_30d_pct: number;
    municipios: Record<string, MunicipioStats>;
}

export interface MunicipioStats {
    count: number;
    median_price: number;
    p25_price: number;
    p75_price: number;
    new_7d: number;
    listings: import('./listing').Listing[];
}

export interface InsightItem {
    municipio: string;
    departamento: string;
    value: number; // % para trends, count para actividad
}

export interface Insights {
    top3_up_30d: InsightItem[];
    top3_down_30d: InsightItem[];
    top3_active_7d: InsightItem[];
}

export interface HomeBIData {
    national: NationalStats;
    departments: DepartmentBIStats[];
    insights: Insights;
    unclassified: {
        count: number;
        listings: import('./listing').Listing[];
    };
}
