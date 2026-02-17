ROLE
Eres Opus 4.6 actuando como Senior Software Architect + Senior SEO + Senior UX/UI. Tu salida debe ser implementación real en el repo (código), sin humo. No inventes estilos: reutiliza los existentes.

OBJETIVO
Crear la nueva página ABOUT para “SIVAR CASAS” en `/about` y agregarla al Navigation Bar (header) siguiendo exactamente el estilo existente del navbar y de los títulos/subtítulos del sitio. La página debe ser estratégica, clara, premium y enfocada en confianza + SEO.

REGLAS NO NEGOCIABLES
1) Reutilizar tipografía/colores/jerarquía EXACTA del header ya existente donde se ve:
   - Título grande + subtítulo (ej: “Panorama del mercado inmobiliario en El Salvador”).
   NO crear estilos nuevos para headings. Busca ese bloque/componente y reutilízalo 1:1 (mismas clases Tailwind o mismo componente).
2) Navbar: agregar “ABOUT” (o “SOBRE”) como item nuevo usando el MISMO componente/estilo/patrón de links (active state, hover, spacing).
3) Página About debe ser liviana: Server Component, sin dependencias nuevas, sin ECharts, sin mapas, sin llamadas innecesarias.
4) Animaciones: solo micro-interacciones CSS + reveal-on-scroll con IntersectionObserver si ya existe patrón. Respetar `prefers-reduced-motion`.
5) Evitar claims absolutos tipo “ningún otro portal…”; usar copy defendible.
6) SEO: metadata propia + canonical + agregar `/about` al sitemap.
7) FAQ: implementar 2 bloques de FAQ (ver abajo) con respuestas cortas “snippet-friendly” + JSON-LD `FAQPage`.

PASOS DE IMPLEMENTACIÓN (OBLIGATORIO)
A) ENCONTRAR “FUENTE DE VERDAD” DE ESTILOS
1) Localiza en el repo el componente/sección que renderiza el header con:
   “Panorama del mercado inmobiliario en El Salvador”
   y extrae el patrón exacto (estructura + clases).
2) Localiza el Navbar/Header actual y el componente de Link/Item que usa para navegación.

B) CREAR RUTA ABOUT
1) Crear `src/app/about/page.tsx` (Server Component).
2) Estructura general:
   - Sección Header reutilizada 1:1 del patrón existente (mismo background, h1, subtítulo).
   - Contenido dividido en secciones (ver “ESTRUCTURA UI/UX”).
3) Crear `src/app/about/metadata` usando `export const metadata` o `generateMetadata()` (según convención del repo):
   - title: “Sobre Sivar Casas | Datos, privacidad y fuentes”
   - description: “Sivar Casas organiza publicaciones públicas de propiedades en El Salvador para ayudarte a comparar mejor y llegar siempre a la fuente original.”
   - alternates/canonical a `/about` (usar el patrón del proyecto).

C) AGREGAR A NAVBAR
1) Agregar item “ABOUT” (o “SOBRE”) al navbar/header existente.
2) Debe respetar:
   - mismo orden visual y estilo de los otros links
   - mismo active state
   - responsive (desktop + mobile)
3) Ubicación recomendada: junto a links informativos (ej: Tendencias/Valuador) antes del CTA principal (si existe).

D) SITEMAP
1) Editar `src/app/sitemap.ts` e incluir `/about` con `lastModified` y el mismo formato que ya usa el sitio.

E) FAQ + SEO SCHEMA
1) Al final del About, renderizar 2 bloques FAQ en UI (acordeón accesible):
   - Bloque 1: “PREGUNTAS FRECUENTES DE BIENES RAÍCES”
   - Bloque 2: “PREGUNTAS FRECUENTES SOBRE SIVAR CASAS (DATOS Y ACTUALIZACIÓN)”
2) Inyectar JSON-LD `FAQPage` en About con TODAS las preguntas de ambos bloques.
   - Si ya existe un helper de JSON-LD (por ejemplo `JsonLd` + generadores en `seo.ts`), extiéndelo con `generateFaqSchema(faqItems)`.
   - Si no existe, agrega un `<script type="application/ld+json">` en About solo para esta página.

ESTRUCTURA UI/UX (SECCIÓN POR SECCIÓN, IMPLEMENTAR TAL CUAL)
NOTA: Mantener títulos en MAYÚSCULAS.

SECCIÓN 1 — HEADER (REUTILIZADO 1:1 DEL SITIO)
- Reutiliza EXACTAMENTE el estilo del header “Panorama…”:
  - Fondo, spacing, tamaño de H1, color del subtítulo.
- Texto:
  H1: “SOBRE SIVAR CASAS”
  Subtítulo: “Organizamos publicaciones públicas de propiedades en El Salvador para que compares mejor, entiendas el mercado y llegues siempre a la fuente original.”

Animación:
- Fade/translate sutil al cargar (solo si el sitio ya usa animación; si no, omitir).

SECCIÓN 2 — QUÉ ES / QUÉ NO ES (2 CARDS)
Diseño:
- Grid 2 columnas en desktop, 1 columna en mobile.
- Cards con mismo estilo de shadow/radius del resto del sitio.

Contenido:
- QUÉ ES:
  “Un agregador y plataforma de análisis que organiza publicaciones públicas, normaliza datos y facilita comparar opciones.”
- QUÉ NO ES:
  “No somos inmobiliaria, no representamos vendedores, no cerramos tratos. La negociación se hace en la fuente original.”

Animación:
- Hover lift sutil (2–4px) + transición de sombra/borde.
- Reveal on scroll (si hay patrón existente).

SECCIÓN 3 — BENEFICIOS (GRID DE 6 MINI-CARDS)
Diseño:
- 2×3 en desktop, 2×2 o 1×6 en mobile según ancho real (priorizar 2×2 si cabe).
- Títulos cortos + descripción 1 línea.

Beneficios:
1) “COMPARAR MÁS RÁPIDO”
2) “TENDENCIAS DEL MERCADO”
3) “VALUADOR”
4) “MAPA DE PRECIOS/m²”
5) “FAVORITOS”
6) “DETALLE CON FUENTE ORIGINAL”

Cada mini-card debe ser clickeable y llevar a rutas existentes (verificar en el repo):
- Tendencias -> ruta real del sitio
- Valuador -> ruta real del sitio
- Favoritos -> ruta real
- Mapa -> ruta real
- Comparador -> solo si existe; si NO existe, mostrar card en estado “Próximamente” sin link.

Animación:
- Hover underline / icon shift leve (sin librerías).

SECCIÓN 4 — HERRAMIENTAS QUE NOS HACEN DIFERENTES (REUTILIZAR LAS CARDS EXISTENTES)
IMPORTANTE: Ya existe un bloque visual con cards de herramientas (Dashboard/Herramienta/Análisis/Mapa). Reutilízalo:
- Misma UI, mismos iconos, mismo spacing.
- Ajustar copy para evitar claim absoluto “ningún otro…”.

Título:
“HERRAMIENTAS QUE NOS HACEN DIFERENTES”
Subtítulo:
“Funcionalidades enfocadas en análisis y comparación del mercado inmobiliario en El Salvador.”

Cards (si existen rutas):
- “TENDENCIAS DEL MERCADO”
- “VALUADOR DE PROPIEDADES”
- “COMPARADOR”
- “MAPA DE PRECIOS/m²”

Animación:
- Hover lift + focus ring accesible.

SECCIÓN 5 — CÓMO FUNCIONA (TIMELINE DE 3 PASOS)
Diseño:
- 3 pasos con icono + título + 2 líneas.
- Horizontal en desktop, vertical en mobile.

Pasos:
1) “LEEMOS PUBLICACIONES PÚBLICAS”
2) “NORMALIZAMOS Y DEPURAMOS”
3) “MOSTRAMOS INSIGHTS Y ENLAZAMOS A LA FUENTE”

Animación:
- Reveal on scroll (simple, no SVG pesada).

SECCIÓN 6 — DE DÓNDE VIENEN LOS DATOS (TRANSPARENCIA)
Diseño:
- Bloque principal + lista de garantías (checklist visual).
- Chips de “Fuentes” (solo texto, no logos) si aplica.

Contenido (obligatorio, claro):
- “Extraemos datos de publicaciones públicamente habilitadas.”
- “Respetamos la privacidad: no capturamos contenido privado o restringido (ej.: publicaciones privadas tipo Marketplace).”
- “Evitamos almacenar datos sensibles personales; nos enfocamos en información del inmueble (precio, ubicación, características).”
- “Cada propiedad incluye un enlace a la publicación original.”

SECCIÓN 7 — CADA CUÁNTO ACTUALIZAMOS (DATO DURO)
Diseño:
- Card grande con 2 sub-cards:
  - “NUEVAS PUBLICACIONES”
  - “REVISIÓN DE ACTIVOS”

Contenido:
- “Nuevas publicaciones: cada hora.”
- “Revisión de anuncios activos: cada 12 horas.”
(Verifica en workflows del repo y ajusta el texto si los cron reales son distintos.)

Nota pequeña:
“Las fuentes pueden cambiar o eliminar anuncios sin aviso; la referencia final siempre es la publicación original.”

SECCIÓN 8 — QUIÉNES SOMOS / MISIÓN / VISIÓN (3 BLOQUES)
Diseño:
- 3 columnas en desktop, acordeón en mobile si el espacio queda estrecho.
Contenido:
- QUIÉNES SOMOS: 2–3 líneas directas.
- MISIÓN: 1 línea fuerte + 1 de apoyo.
- VISIÓN: 1 línea fuerte + 1 de apoyo.

SECCIÓN 9 — DISCLAIMER Y ATRIBUCIÓN (LEGAL AMIGABLE)
Diseño:
- Caja “info” con estilo sobrio.
Contenido obligatorio:
- “No almacenamos información sensible.”
- “Las imágenes se muestran únicamente con fines de visibilidad.”
- “Los créditos pertenecen a las fuentes originales.”
- “Para iniciar compra/venta/renta debes hacerlo en la fuente correspondiente.”
- “Cada propiedad enlaza a su publicación original.”

SECCIÓN 10 — FAQ (2 BLOQUES) + JSON-LD FAQPage
Diseño UI:
- Acordeón accesible: headings, aria-expanded, teclado.
- Respuestas 1–3 frases, directo.

BLOQUE 1: “PREGUNTAS FRECUENTES DE BIENES RAÍCES” (5)
Q1: ¿QUÉ ES MEJOR: COMPRAR O ALQUILAR EN EL SALVADOR?
A: Depende de tu horizonte y estabilidad. Comprar conviene si piensas quedarte varios años y puedes asumir gastos de cierre y mantenimiento; alquilar es mejor si necesitas flexibilidad, estás probando zona o no quieres inmovilizar capital.

Q2: ¿QUÉ DEBO REVISAR ANTES DE COMPRAR UNA PROPIEDAD?
A: Título de propiedad, impuestos/solvencias, estado legal del inmueble, acceso a servicios y estado físico. Si algo no cuadra, lo correcto es validarlo con un profesional y con la información oficial correspondiente.

Q3: ¿CÓMO SABER SI EL PRECIO DE UNA CASA ESTÁ ALTO O BAJO?
A: Compará con propiedades similares en la misma zona (m², habitaciones, parqueos y estado). Si el precio se sale mucho del promedio, normalmente hay una razón: ubicación específica, acabados, urgencia de venta o datos incompletos.

Q4: ¿QUÉ ZONAS TIENDEN A SER MÁS CARAS Y POR QUÉ?
A: Las zonas con mejor acceso, servicios, demanda constante y menor oferta suelen tener mayor precio por m². También influyen seguridad percibida, cercanía a centros de trabajo y calidad de infraestructura.

Q5: ¿QUÉ ERRORES COMUNES COMETE LA GENTE AL BUSCAR CASA?
A: Ir solo por precio sin ver costos reales (mantenimiento, parqueo, servicios), no comparar suficientes opciones y no revisar el estado legal. Otro error es decidir sin considerar tiempos de traslado y cambios de tráfico por horarios.

BLOQUE 2: “PREGUNTAS FRECUENTES SOBRE SIVAR CASAS (DATOS Y ACTUALIZACIÓN)” (5)
Q1: ¿DE DÓNDE VIENEN LOS DATOS DE SIVAR CASAS?
A: Provienen de publicaciones públicamente habilitadas en distintas fuentes. Sivar Casas organiza esa información para facilitar comparación y siempre enlaza a la publicación original.

Q2: ¿SIVAR CASAS GUARDA DATOS PERSONALES COMO CORREOS O INFORMACIÓN PRIVADA?
A: No. Respetamos la privacidad de las fuentes y evitamos capturar o almacenar datos sensibles personales. El foco es la información del inmueble necesaria para comparar y enlazar al anuncio original.

Q3: ¿CADA CUÁNTO SE ACTUALIZA LA INFORMACIÓN?
A: Buscamos nuevas publicaciones con alta frecuencia y re-verificamos anuncios activos periódicamente. En el sistema actual, el objetivo es detectar nuevos anuncios cada hora y revisar activos cada 12 horas (verificar crons reales y ajustar si aplica).

Q4: ¿PUEDO COMPRAR, VENDER O CONTACTAR ANUNCIANTES DIRECTAMENTE EN SIVAR CASAS?
A: No. Sivar Casas no intermedia transacciones. Para compra/venta/renta o contacto debes hacerlo desde la publicación original en la fuente correspondiente.

Q5: ¿QUÉ HAGO SI UN ANUNCIO TIENE INFORMACIÓN INCORRECTA O QUIERO QUE SE ELIMINE?
A: Podés reportarlo desde el enlace del anuncio o por el canal de contacto del sitio. Se revisa el caso y, si corresponde, se corrige la referencia o se ajusta la visibilidad.

CTA FINAL (AL CIERRE)
- Banda final con 2 botones:
  - “EXPLORAR PROPIEDADES”
  - “VER TENDENCIAS”
Estilo: el mismo de los CTAs del sitio.

CRITERIOS DE ACEPTACIÓN
- `/about` existe, compila y respeta el diseño del sitio.
- Header de About es idéntico al patrón “Panorama…” (mismas clases o mismo componente).
- Navbar tiene item ABOUT/SOBRE con estilo idéntico a los demás.
- `/about` aparece en sitemap.
- FAQ visible en UI + JSON-LD FAQPage válido.
- No se introdujeron librerías nuevas.
- Animaciones sutiles y respetan reduced motion.
- No hay claims absolutos “ningún otro portal…”.

EJECUTA AHORA
1) Escanea repo para encontrar el header “Panorama…” y el Navbar.
2) Implementa `/about` con la estructura exacta.
3) Añade link al Navbar.
4) Actualiza sitemap.
5) Añade FAQ UI + FAQPage JSON-LD.
6) Verifica build y lint.
