export interface DepartmentStats {
    departamento: string;
    sale: { count: number; min: number; max: number; avg: number } | null;
    rent: { count: number; min: number; max: number; avg: number } | null;
    total_count: number;
}

export interface DepartmentStatsRow {
    departamento: string;
    listing_type: string;
    min_price: number;
    max_price: number;
    avg_price: number;
    count: number;
}
