// Mapeo completo de los 14 departamentos de El Salvador y sus municipios
// Incluye aliases para lugares conocidos

export interface DepartamentoInfo {
    nombre: string;
    municipios: string[];
}

// Los 14 departamentos de El Salvador con sus municipios
export const DEPARTAMENTOS: Record<string, string[]> = {
    "San Salvador": [
        "San Salvador", "Soyapango", "Mejicanos", "Apopa", "Ciudad Delgado",
        "Ilopango", "Tonacatepeque", "San Martín", "Cuscatancingo", "Ayutuxtepeque",
        "San Marcos", "Panchimalco", "El Paisnal", "Aguilares", "Guazapa",
        "Rosario de Mora", "Santiago Texacuangos", "Santo Tomás", "Nejapa"
    ],
    "La Libertad": [
        "Santa Tecla", "Antiguo Cuscatlán", "Colón", "San Juan Opico", "Quezaltepeque",
        "Zaragoza", "Nuevo Cuscatlán", "Ciudad Arce", "Jayaque", "Tepecoyo",
        "Sacacoyo", "Huizúcar", "Talnique", "Comasagua", "Chiltiupán",
        "La Libertad", "Tamanique", "Teotepeque", "Jicalapa"
    ],
    "Santa Ana": [
        "Santa Ana", "Metapán", "Chalchuapa", "Coatepeque", "El Congo",
        "Texistepeque", "Candelaria de la Frontera", "El Porvenir", "Masahuat",
        "San Antonio Pajonal", "San Sebastián Salitrillo", "Santa Rosa Guachipilín", "Santiago de la Frontera"
    ],
    "San Miguel": [
        "San Miguel", "Ciudad Barrios", "Chinameca", "Moncagua", "Sesori",
        "Chapeltique", "Chirilagua", "Comacarán", "El Tránsito", "Lolotique",
        "Nueva Guadalupe", "Nuevo Edén de San Juan", "Quelepa", "San Antonio del Mosco",
        "San Gerardo", "San Jorge", "San Luis de la Reina", "San Rafael Oriente", "Uluazapa"
    ],
    "La Paz": [
        "Zacatecoluca", "San Luis Talpa", "San Pedro Masahuat", "Olocuilta",
        "Santiago Nonualco", "San Juan Nonualco", "San Pedro Nonualco", "San Rafael Obrajuelo",
        "Cuyultitán", "El Rosario", "Jerusalén", "Mercedes La Ceiba", "Paraíso de Osorio",
        "San Antonio Masahuat", "San Emigdio", "San Francisco Chinameca", "San Juan Talpa",
        "San Juan Tepezontes", "San Miguel Tepezontes", "Santa María Ostuma", "Tapalhuaca"
    ],
    "Usulután": [
        "Usulután", "Jiquilisco", "San Agustín", "Berlín", "Alegría",
        "Santiago de María", "Jucuapa", "El Triunfo", "Estanzuelas", "Mercedes Umaña",
        "Nueva Granada", "Ozatlán", "Puerto El Triunfo", "San Buenaventura", "San Dionisio",
        "San Francisco Javier", "Santa Elena", "Santa María", "Tecapán", "California",
        "Concepción Batres", "Ereguayquín"
    ],
    "Sonsonate": [
        "Sonsonate", "Izalco", "Nahuizalco", "Juayúa", "Acajutla",
        "Armenia", "San Antonio del Monte", "San Julián", "Santa Catarina Masahuat",
        "Santa Isabel Ishuatán", "Cuisnahuat", "Caluco", "Nahulingo", "Salcoatitán",
        "Sonzacate", "Santo Domingo de Guzmán"
    ],
    "La Unión": [
        "La Unión", "Santa Rosa de Lima", "Conchagua", "El Carmen", "Intipucá",
        "San Alejo", "Yucuaiquín", "Anamorós", "Bolívar", "Concepción de Oriente",
        "El Sauce", "Lislique", "Meanguera del Golfo", "Nueva Esparta", "Pasaquina",
        "Polorós", "San José", "Yayantique"
    ],
    "Ahuachapán": [
        "Ahuachapán", "Atiquizaya", "Jujutla", "Tacuba", "Concepción de Ataco",
        "Apaneca", "El Refugio", "Guaymango", "San Francisco Menéndez",
        "San Lorenzo", "San Pedro Puxtla", "Turín"
    ],
    "Cuscatlán": [
        "Cojutepeque", "Suchitoto", "San Pedro Perulapán", "San Rafael Cedros",
        "San Bartolomé Perulapía", "Candelaria", "Tenancingo", "Monte San Juan",
        "El Carmen", "El Rosario", "San Cristóbal", "San José Guayabal",
        "San Ramón", "Santa Cruz Analquito", "Santa Cruz Michapa", "Oratorio de Concepción"
    ],
    "Chalatenango": [
        "Chalatenango", "Nueva Concepción", "La Palma", "San Ignacio", "Tejutla",
        "Dulce Nombre de María", "Arcatao", "Azacualpa", "Cancasque", "Citalá",
        "Comalapa", "Concepción Quezaltepeque", "El Carrizal", "El Paraíso",
        "La Laguna", "La Reina", "Las Flores", "Las Vueltas", "Nombre de Jesús",
        "Nueva Trinidad", "Ojos de Agua", "Potonico", "San Antonio de la Cruz",
        "San Antonio Los Ranchos", "San Fernando", "San Francisco Lempa",
        "San Francisco Morazán", "San Isidro Labrador", "San José Cancasque",
        "San José Las Flores", "San Luis del Carmen", "San Miguel de Mercedes",
        "San Rafael", "Santa Rita"
    ],
    "Morazán": [
        "San Francisco Gotera", "Corinto", "Sociedad", "Cacaopera", "Joateca",
        "Arambala", "Chilanga", "Delicias de Concepción", "El Divisadero",
        "El Rosario", "Gualococti", "Guatajiagua", "Jocoaitique", "Jocoro",
        "Lolotiquillo", "Meanguera", "Osicala", "Perquín", "San Carlos",
        "San Fernando", "San Isidro", "San Simón", "Sensembra", "Torola", "Yamabal", "Yoloaiquín"
    ],
    "Cabañas": [
        "Sensuntepeque", "Ilobasco", "Jutiapa", "Victoria", "Dolores",
        "Cinquera", "Guacotecti", "San Isidro", "Tejutepeque"
    ],
    "San Vicente": [
        "San Vicente", "Tecoluca", "Apastepeque", "Guadalupe", "San Sebastián",
        "Santa Clara", "San Cayetano Istepeque", "San Esteban Catarina",
        "San Ildefonso", "San Lorenzo", "Santo Domingo", "Tepetitán", "Verapaz"
    ]
};

// Aliases para lugares conocidos que deben mapearse a municipios específicos
export const LOCATION_ALIASES: Record<string, { municipio: string; departamento: string }> = {
    // La Libertad - Santa Tecla
    "merliot": { municipio: "Antiguo Cuscatlán", departamento: "La Libertad" },
    "jardines de merliot": { municipio: "Antiguo Cuscatlán", departamento: "La Libertad" },
    "jardines del volcan": { municipio: "Santa Tecla", departamento: "La Libertad" },
    "residencial utila": { municipio: "Santa Tecla", departamento: "La Libertad" },
    "lomas de san francisco": { municipio: "Antiguo Cuscatlán", departamento: "La Libertad" },

    // San Salvador - Colonias conocidas
    "colonia escalón": { municipio: "San Salvador", departamento: "San Salvador" },
    "escalon": { municipio: "San Salvador", departamento: "San Salvador" },
    "escalón": { municipio: "San Salvador", departamento: "San Salvador" },
    "colonia san benito": { municipio: "San Salvador", departamento: "San Salvador" },
    "san benito": { municipio: "San Salvador", departamento: "San Salvador" },
    "zona rosa": { municipio: "San Salvador", departamento: "San Salvador" },
    "centro histórico": { municipio: "San Salvador", departamento: "San Salvador" },
    "metrocentro": { municipio: "San Salvador", departamento: "San Salvador" },
    "colonia médica": { municipio: "San Salvador", departamento: "San Salvador" },
    "miralvalle": { municipio: "San Salvador", departamento: "San Salvador" },
    "planes de renderos": { municipio: "Panchimalco", departamento: "San Salvador" },
    "los planes": { municipio: "Panchimalco", departamento: "San Salvador" },

    // Sonsonate
    "ruta de las flores": { municipio: "Juayúa", departamento: "Sonsonate" },
    "los naranjos": { municipio: "Juayúa", departamento: "Sonsonate" },

    // La Libertad - Playa
    "playa el tunco": { municipio: "La Libertad", departamento: "La Libertad" },
    "el tunco": { municipio: "La Libertad", departamento: "La Libertad" },
    "playa el sunzal": { municipio: "La Libertad", departamento: "La Libertad" },
    "el sunzal": { municipio: "La Libertad", departamento: "La Libertad" },
    "playa el zonte": { municipio: "Chiltiupán", departamento: "La Libertad" },
    "el zonte": { municipio: "Chiltiupán", departamento: "La Libertad" },
    "puerto de la libertad": { municipio: "La Libertad", departamento: "La Libertad" },

    // Otros
    "el espino": { municipio: "Antiguo Cuscatlán", departamento: "La Libertad" },
    "gran via": { municipio: "Antiguo Cuscatlán", departamento: "La Libertad" },
    "la gran vía": { municipio: "Antiguo Cuscatlán", departamento: "La Libertad" },
    "multiplaza": { municipio: "Antiguo Cuscatlán", departamento: "La Libertad" },
};

// Función para normalizar texto (quitar acentos, minúsculas)
export function normalizeText(text: string): string {
    return text
        .toLowerCase()
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .trim();
}

// Función para detectar el departamento de una ubicación
export function detectDepartamento(location: string): { departamento: string; municipio: string } | null {
    const normalized = normalizeText(location);

    // 1. Buscar en aliases primero
    for (const [alias, info] of Object.entries(LOCATION_ALIASES)) {
        if (normalized.includes(normalizeText(alias))) {
            return info;
        }
    }

    // 2. Buscar en municipios
    for (const [departamento, municipios] of Object.entries(DEPARTAMENTOS)) {
        for (const municipio of municipios) {
            if (normalized.includes(normalizeText(municipio))) {
                return { departamento, municipio };
            }
        }
    }

    // 3. Buscar el nombre del departamento directamente
    for (const departamento of Object.keys(DEPARTAMENTOS)) {
        if (normalized.includes(normalizeText(departamento))) {
            return { departamento, municipio: departamento };
        }
    }

    return null;
}

// Obtener todos los nombres de departamentos
export function getDepartamentoNames(): string[] {
    return Object.keys(DEPARTAMENTOS);
}

// Obtener municipios de un departamento
export function getMunicipios(departamento: string): string[] {
    return DEPARTAMENTOS[departamento] || [];
}
