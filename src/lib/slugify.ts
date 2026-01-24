// Utilidades para convertir nombres de departamento a slugs y viceversa

const DEPARTAMENTO_MAP: Record<string, string> = {
    'ahuachapan': 'Ahuachapán',
    'cabanas': 'Cabañas',
    'chalatenango': 'Chalatenango',
    'cuscatlan': 'Cuscatlán',
    'la-libertad': 'La Libertad',
    'la-paz': 'La Paz',
    'la-union': 'La Unión',
    'morazan': 'Morazán',
    'san-miguel': 'San Miguel',
    'san-salvador': 'San Salvador',
    'san-vicente': 'San Vicente',
    'santa-ana': 'Santa Ana',
    'sonsonate': 'Sonsonate',
    'usulutan': 'Usulután',
};

// Inverso del mapa
const SLUG_MAP: Record<string, string> = Object.entries(DEPARTAMENTO_MAP).reduce(
    (acc, [slug, name]) => ({ ...acc, [name]: slug }),
    {}
);

/**
 * Convierte un nombre de departamento a slug URL
 * "San Salvador" → "san-salvador"
 * "La Libertad" → "la-libertad"
 */
export function departamentoToSlug(departamento: string): string {
    return SLUG_MAP[departamento] || departamento
        .toLowerCase()
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .replace(/\s+/g, '-')
        .replace(/[^a-z0-9-]/g, '');
}

/**
 * Convierte un slug URL al nombre de departamento
 * "san-salvador" → "San Salvador"
 * "la-libertad" → "La Libertad"
 */
export function slugToDepartamento(slug: string): string {
    return DEPARTAMENTO_MAP[slug] || slug;
}

/**
 * Obtiene todos los slugs válidos
 */
export function getAllDepartamentoSlugs(): string[] {
    return Object.keys(DEPARTAMENTO_MAP);
}

/**
 * Verifica si un slug es válido
 */
export function isValidDepartamentoSlug(slug: string): boolean {
    return slug in DEPARTAMENTO_MAP;
}
