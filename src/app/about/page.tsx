import type { Metadata } from 'next';
import Link from 'next/link';
import Navbar from '@/components/Navbar';
import SectionHeader from '@/components/SectionHeader';
import { generateFaqSchema } from '@/lib/seo';

export const metadata: Metadata = {
    title: 'Sobre Sivar Casas | Datos, privacidad y fuentes',
    description: 'Sivar Casas organiza publicaciones públicas de propiedades en El Salvador para ayudarte a comparar mejor y llegar siempre a la fuente original.',
    alternates: {
        canonical: '/about',
    },
};

/* ═══════════════════════════════════════════
   FAQ DATA
   ═══════════════════════════════════════════ */

const FAQ_REAL_ESTATE = [
    {
        question: '¿Qué es mejor: comprar o alquilar en El Salvador?',
        answer: 'Depende de tu horizonte y estabilidad. Comprar conviene si piensas quedarte varios años y puedes asumir gastos de cierre y mantenimiento; alquilar es mejor si necesitas flexibilidad, estás probando zona o no quieres inmovilizar capital.',
    },
    {
        question: '¿Qué debo revisar antes de comprar una propiedad?',
        answer: 'Título de propiedad, impuestos/solvencias, estado legal del inmueble, acceso a servicios y estado físico. Si algo no cuadra, lo correcto es validarlo con un profesional y con la información oficial correspondiente.',
    },
    {
        question: '¿Cómo saber si el precio de una casa está alto o bajo?',
        answer: 'Compará con propiedades similares en la misma zona (m², habitaciones, parqueos y estado). Si el precio se sale mucho del promedio, normalmente hay una razón: ubicación específica, acabados, urgencia de venta o datos incompletos.',
    },
    {
        question: '¿Qué zonas tienden a ser más caras y por qué?',
        answer: 'Las zonas con mejor acceso, servicios, demanda constante y menor oferta suelen tener mayor precio por m². También influyen seguridad percibida, cercanía a centros de trabajo y calidad de infraestructura.',
    },
    {
        question: '¿Qué errores comunes comete la gente al buscar casa?',
        answer: 'Ir solo por precio sin ver costos reales (mantenimiento, parqueo, servicios), no comparar suficientes opciones y no revisar el estado legal. Otro error es decidir sin considerar tiempos de traslado y cambios de tráfico por horarios.',
    },
];

const FAQ_SIVAR_CASAS = [
    {
        question: '¿De dónde vienen los datos de Sivar Casas?',
        answer: 'Provienen de publicaciones públicamente habilitadas en distintas fuentes. Sivar Casas organiza esa información para facilitar comparación y siempre enlaza a la publicación original.',
    },
    {
        question: '¿Sivar Casas guarda datos personales como correos o información privada?',
        answer: 'No. Respetamos la privacidad de las fuentes y evitamos capturar o almacenar datos sensibles personales. El foco es la información del inmueble necesaria para comparar y enlazar al anuncio original.',
    },
    {
        question: '¿Cada cuánto se actualiza la información?',
        answer: 'Buscamos nuevas publicaciones cada hora y re-verificamos anuncios activos cada 12 horas. Los datos se normalizan y depuran antes de publicarse.',
    },
    {
        question: '¿Puedo comprar, vender o contactar anunciantes directamente en Sivar Casas?',
        answer: 'No. Sivar Casas no intermedia transacciones. Para compra/venta/renta o contacto debes hacerlo desde la publicación original en la fuente correspondiente.',
    },
    {
        question: '¿Qué hago si un anuncio tiene información incorrecta o quiero que se elimine?',
        answer: 'Podés reportarlo desde el enlace del anuncio o por el canal de contacto del sitio. Se revisa el caso y, si corresponde, se corrige la referencia o se ajusta la visibilidad.',
    },
];

const ALL_FAQ = [...FAQ_REAL_ESTATE, ...FAQ_SIVAR_CASAS];

/* ═══════════════════════════════════════════
   BENEFITS DATA
   ═══════════════════════════════════════════ */

const BENEFITS = [
    { title: 'COMPARAR MÁS RÁPIDO', desc: 'Todas las fuentes en un solo lugar, normalizadas.', href: '/' },
    { title: 'TENDENCIAS DEL MERCADO', desc: 'Rankings, precios promedio y actividad por zona.', href: '/tendencias' },
    { title: 'VALUADOR', desc: 'Estimación automatizada con comparables reales.', href: '/valuador-de-inmuebles' },
    { title: 'MAPA DE PRECIOS/M²', desc: 'Visualiza precios por ubicación en el mapa.', href: '/#departamentos' },
    { title: 'FAVORITOS', desc: 'Guarda hasta 25 propiedades para comparar.', href: '/favoritos' },
    { title: 'DETALLE CON FUENTE ORIGINAL', desc: 'Cada propiedad enlaza a su publicación original.', href: null },
];

const TOOLS = [
    { icon: '📊', title: 'TENDENCIAS DEL MERCADO', desc: 'Rankings de precios, actividad por departamento y evolución mensual.', href: '/tendencias' },
    { icon: '🏠', title: 'VALUADOR DE PROPIEDADES', desc: 'Estimación automatizada basada en comparables cercanos con confianza.', href: '/valuador-de-inmuebles' },
    { icon: '❤️', title: 'FAVORITOS', desc: 'Guarda propiedades, compara métricas y vuelve cuando quieras.', href: '/favoritos' },
    { icon: '🗺️', title: 'MAPA INTERACTIVO', desc: 'Explora propiedades por ubicación con datos de cada departamento.', href: '/#departamentos' },
];

const STEPS = [
    { num: '01', title: 'LEEMOS PUBLICACIONES PÚBLICAS', desc: 'Recopilamos datos de fuentes públicamente habilitadas de forma automatizada.' },
    { num: '02', title: 'NORMALIZAMOS Y DEPURAMOS', desc: 'Unificamos formatos, corregimos clasificaciones y eliminamos duplicados.' },
    { num: '03', title: 'MOSTRAMOS INSIGHTS Y ENLAZAMOS A LA FUENTE', desc: 'Presentamos análisis útil y siempre enlazamos al anuncio original.' },
];

/* ═══════════════════════════════════════════
   COMPONENT
   ═══════════════════════════════════════════ */

export default function AboutPage() {
    const faqSchema = generateFaqSchema(ALL_FAQ);

    return (
        <>
            <Navbar />

            {/* JSON-LD FAQPage */}
            <script
                type="application/ld+json"
                dangerouslySetInnerHTML={{ __html: JSON.stringify(faqSchema) }}
            />

            <main className="container mx-auto px-4 max-w-7xl">

                {/* ══════════════ SECTION 1 — HEADER ══════════════ */}
                <section className="pt-10 pb-10">
                    <SectionHeader
                        title={['SOBRE', 'SIVAR CASAS']}
                        subtitle="Organizamos publicaciones públicas de propiedades en El Salvador para que compares mejor, entiendas el mercado y llegues siempre a la fuente original."
                        asH1
                    />
                </section>

                <hr className="border-t border-slate-200/70 my-0" />

                {/* ══════════════ SECTION 2 — QUÉ ES / QUÉ NO ES ══════════════ */}
                <section className="pt-10 pb-10">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div className="card-float p-6 md:p-8">
                            <div className="flex items-center gap-3 mb-4">
                                <span className="w-10 h-10 rounded-xl bg-[var(--primary)] text-white flex items-center justify-center text-lg">✓</span>
                                <h2 className="text-lg font-bold text-[var(--text-primary)] uppercase tracking-wide">QUÉ ES</h2>
                            </div>
                            <p className="text-[var(--text-secondary)] leading-relaxed">
                                Un agregador y plataforma de análisis que organiza publicaciones públicas, normaliza datos y facilita comparar opciones.
                            </p>
                        </div>
                        <div className="card-float p-6 md:p-8">
                            <div className="flex items-center gap-3 mb-4">
                                <span className="w-10 h-10 rounded-xl bg-slate-500 text-white flex items-center justify-center text-lg">✗</span>
                                <h2 className="text-lg font-bold text-[var(--text-primary)] uppercase tracking-wide">QUÉ NO ES</h2>
                            </div>
                            <p className="text-[var(--text-secondary)] leading-relaxed">
                                No somos inmobiliaria, no representamos vendedores, no cerramos tratos. La negociación se hace en la fuente original.
                            </p>
                        </div>
                    </div>
                </section>

                <hr className="border-t border-slate-200/70 my-0" />

                {/* ══════════════ SECTION 3 — BENEFICIOS ══════════════ */}
                <section className="pt-10 pb-10">
                    <SectionHeader
                        title={['BENEFICIOS PARA', 'TI']}
                        subtitle="Lo que obtienes al usar Sivar Casas."
                    />
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                        {BENEFITS.map((b) => (
                            <div key={b.title} className="card-float p-5 group">
                                <h3 className="text-sm font-bold text-[var(--primary)] uppercase tracking-wider mb-2">{b.title}</h3>
                                <p className="text-sm text-[var(--text-secondary)] leading-relaxed mb-3">{b.desc}</p>
                                {b.href ? (
                                    <Link
                                        href={b.href}
                                        className="text-xs font-semibold text-[var(--primary)] hover:opacity-80 transition-opacity no-underline inline-flex items-center gap-1"
                                    >
                                        Explorar
                                        <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><path d="M6 4L10 8L6 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
                                    </Link>
                                ) : (
                                    <span className="text-xs font-medium text-[var(--text-muted)] italic">Disponible en cada listado</span>
                                )}
                            </div>
                        ))}
                    </div>
                </section>

                <hr className="border-t border-slate-200/70 my-0" />

                {/* ══════════════ SECTION 4 — HERRAMIENTAS ══════════════ */}
                <section className="pt-10 pb-10">
                    <SectionHeader
                        title={['HERRAMIENTAS QUE NOS HACEN', 'DIFERENTES']}
                        subtitle="Funcionalidades enfocadas en análisis y comparación del mercado inmobiliario en El Salvador."
                    />
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
                        {TOOLS.map((t) => (
                            <Link key={t.title} href={t.href} className="card-float p-6 no-underline group block">
                                <span className="text-2xl mb-3 block">{t.icon}</span>
                                <h3 className="text-sm font-bold text-[var(--text-primary)] uppercase tracking-wider mb-2">{t.title}</h3>
                                <p className="text-sm text-[var(--text-secondary)] leading-relaxed">{t.desc}</p>
                            </Link>
                        ))}
                    </div>
                </section>

                <hr className="border-t border-slate-200/70 my-0" />

                {/* ══════════════ SECTION 5 — CÓMO FUNCIONA ══════════════ */}
                <section className="pt-10 pb-10">
                    <SectionHeader
                        title={['CÓMO', 'FUNCIONA']}
                    />
                    <div className="flex flex-col md:flex-row gap-6">
                        {STEPS.map((s, i) => (
                            <div key={s.num} className="card-float p-6 flex-1 relative">
                                <span className="text-3xl font-black text-[var(--primary)] opacity-20 absolute top-4 right-4">{s.num}</span>
                                <h3 className="text-sm font-bold text-[var(--text-primary)] uppercase tracking-wider mb-2 pr-12">{s.title}</h3>
                                <p className="text-sm text-[var(--text-secondary)] leading-relaxed">{s.desc}</p>
                                {i < STEPS.length - 1 && (
                                    <div className="hidden md:block absolute -right-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)] text-lg z-10">→</div>
                                )}
                            </div>
                        ))}
                    </div>
                </section>

                <hr className="border-t border-slate-200/70 my-0" />

                {/* ══════════════ SECTION 6 — DE DÓNDE VIENEN LOS DATOS ══════════════ */}
                <section className="pt-10 pb-10">
                    <SectionHeader
                        title={['DE DÓNDE VIENEN', 'LOS DATOS']}
                        subtitle="Transparencia sobre las fuentes y el manejo de la información."
                    />
                    <div className="card-float p-6 md:p-8">
                        <ul className="space-y-4">
                            {[
                                'Extraemos datos de publicaciones públicamente habilitadas.',
                                'Respetamos la privacidad: no capturamos contenido privado o restringido.',
                                'Evitamos almacenar datos sensibles personales; nos enfocamos en información del inmueble (precio, ubicación, características).',
                                'Cada propiedad incluye un enlace a la publicación original.',
                            ].map((text) => (
                                <li key={text} className="flex items-start gap-3">
                                    <svg className="w-5 h-5 text-[var(--success)] mt-0.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                    </svg>
                                    <span className="text-sm text-[var(--text-secondary)] leading-relaxed">{text}</span>
                                </li>
                            ))}
                        </ul>
                    </div>
                </section>

                <hr className="border-t border-slate-200/70 my-0" />

                {/* ══════════════ SECTION 7 — CADA CUÁNTO ACTUALIZAMOS ══════════════ */}
                <section className="pt-10 pb-10">
                    <SectionHeader
                        title={['CADA CUÁNTO', 'ACTUALIZAMOS']}
                    />
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div className="card-float p-6 text-center">
                            <div className="text-3xl font-black text-[var(--primary)] mb-2">1h</div>
                            <h3 className="text-sm font-bold text-[var(--text-primary)] uppercase tracking-wider mb-2">NUEVAS PUBLICACIONES</h3>
                            <p className="text-sm text-[var(--text-secondary)]">Buscamos nuevos anuncios cada hora en todas las fuentes.</p>
                        </div>
                        <div className="card-float p-6 text-center">
                            <div className="text-3xl font-black text-[var(--primary)] mb-2">12h</div>
                            <h3 className="text-sm font-bold text-[var(--text-primary)] uppercase tracking-wider mb-2">REVISIÓN DE ACTIVOS</h3>
                            <p className="text-sm text-[var(--text-secondary)]">Re-verificamos anuncios activos cada 12 horas para detectar cambios o eliminaciones.</p>
                        </div>
                    </div>
                    <p className="text-xs text-[var(--text-muted)] text-center mt-4 italic opacity-75">
                        Las fuentes pueden cambiar o eliminar anuncios sin aviso; la referencia final siempre es la publicación original.
                    </p>
                </section>

                <hr className="border-t border-slate-200/70 my-0" />

                {/* ══════════════ SECTION 8 — QUIÉNES SOMOS ══════════════ */}
                <section className="pt-10 pb-10">
                    <SectionHeader
                        title={['QUIÉNES', 'SOMOS']}
                    />
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        <div className="card-float p-6">
                            <h3 className="text-sm font-bold text-[var(--primary)] uppercase tracking-wider mb-3">QUIÉNES SOMOS</h3>
                            <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
                                Un equipo enfocado en hacer más accesible y transparente la información del mercado inmobiliario en El Salvador.
                            </p>
                        </div>
                        <div className="card-float p-6">
                            <h3 className="text-sm font-bold text-[var(--primary)] uppercase tracking-wider mb-3">MISIÓN</h3>
                            <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
                                <strong>Organizar datos públicos de propiedades</strong> para que cualquier persona pueda comparar, analizar y tomar decisiones con mayor confianza.
                            </p>
                        </div>
                        <div className="card-float p-6">
                            <h3 className="text-sm font-bold text-[var(--primary)] uppercase tracking-wider mb-3">VISIÓN</h3>
                            <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
                                <strong>Ser la referencia de inteligencia inmobiliaria en El Salvador,</strong> donde los datos hablen claro y cada usuario llegue a la fuente con toda la información.
                            </p>
                        </div>
                    </div>
                </section>

                <hr className="border-t border-slate-200/70 my-0" />

                {/* ══════════════ SECTION 9 — DISCLAIMER ══════════════ */}
                <section className="pt-10 pb-10">
                    <div className="rounded-xl bg-[var(--bg-subtle)] border border-slate-200 p-6 md:p-8">
                        <h2 className="text-sm font-bold text-[var(--text-primary)] uppercase tracking-wider mb-4">DISCLAIMER Y ATRIBUCIÓN</h2>
                        <ul className="space-y-2">
                            {[
                                'No almacenamos información sensible.',
                                'Las imágenes se muestran únicamente con fines de visibilidad.',
                                'Los créditos pertenecen a las fuentes originales.',
                                'Para iniciar compra/venta/renta debes hacerlo en la fuente correspondiente.',
                                'Cada propiedad enlaza a su publicación original.',
                            ].map((text) => (
                                <li key={text} className="flex items-start gap-2 text-sm text-[var(--text-secondary)]">
                                    <span className="text-[var(--text-muted)] mt-0.5">•</span>
                                    {text}
                                </li>
                            ))}
                        </ul>
                    </div>
                </section>

                <hr className="border-t border-slate-200/70 my-0" />

                {/* ══════════════ SECTION 10 — FAQ ══════════════ */}
                <section className="pt-10 pb-10">
                    {/* Block 1 */}
                    <div className="mb-10">
                        <h2 className="text-xl md:text-2xl font-black text-[var(--text-primary)] tracking-tight mb-6">
                            PREGUNTAS FRECUENTES <span className="text-[var(--primary)]">DE BIENES RAÍCES</span>
                        </h2>
                        <div className="space-y-3">
                            {FAQ_REAL_ESTATE.map((faq) => (
                                <details key={faq.question} className="card-float group">
                                    <summary className="flex items-center justify-between cursor-pointer px-5 py-4 text-sm font-semibold text-[var(--text-primary)] select-none list-none [&::-webkit-details-marker]:hidden">
                                        <span className="pr-4">{faq.question.toUpperCase()}</span>
                                        <svg className="w-4 h-4 shrink-0 text-[var(--text-muted)] transition-transform group-open:rotate-180" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                        </svg>
                                    </summary>
                                    <div className="px-5 pb-4 text-sm text-[var(--text-secondary)] leading-relaxed border-t border-slate-100 pt-3">
                                        {faq.answer}
                                    </div>
                                </details>
                            ))}
                        </div>
                    </div>

                    {/* Block 2 */}
                    <div>
                        <h2 className="text-xl md:text-2xl font-black text-[var(--text-primary)] tracking-tight mb-6">
                            PREGUNTAS FRECUENTES SOBRE <span className="text-[var(--primary)]">SIVAR CASAS</span>
                        </h2>
                        <div className="space-y-3">
                            {FAQ_SIVAR_CASAS.map((faq) => (
                                <details key={faq.question} className="card-float group">
                                    <summary className="flex items-center justify-between cursor-pointer px-5 py-4 text-sm font-semibold text-[var(--text-primary)] select-none list-none [&::-webkit-details-marker]:hidden">
                                        <span className="pr-4">{faq.question.toUpperCase()}</span>
                                        <svg className="w-4 h-4 shrink-0 text-[var(--text-muted)] transition-transform group-open:rotate-180" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                        </svg>
                                    </summary>
                                    <div className="px-5 pb-4 text-sm text-[var(--text-secondary)] leading-relaxed border-t border-slate-100 pt-3">
                                        {faq.answer}
                                    </div>
                                </details>
                            ))}
                        </div>
                    </div>
                </section>

                <hr className="border-t border-slate-200/70 my-0" />

                {/* ══════════════ CTA FINAL ══════════════ */}
                <section className="pt-10 pb-16">
                    <div className="bg-gradient-to-r from-[var(--primary)] to-[#2d5a8e] rounded-xl p-8 md:p-12 text-center text-white">
                        <h2 className="text-xl md:text-2xl font-black mb-3 uppercase">EMPEZÁ A EXPLORAR</h2>
                        <p className="text-sm text-blue-100 mb-6 max-w-xl mx-auto">
                            Compará propiedades, descubrí tendencias y tomá decisiones con datos reales del mercado inmobiliario en El Salvador.
                        </p>
                        <div className="flex flex-col sm:flex-row gap-3 justify-center">
                            <Link
                                href="/"
                                className="inline-flex items-center justify-center gap-2 px-6 py-3 bg-white text-[var(--primary)] font-semibold rounded-lg hover:bg-blue-50 transition-colors text-sm no-underline"
                            >
                                EXPLORAR PROPIEDADES
                            </Link>
                            <Link
                                href="/tendencias"
                                className="inline-flex items-center justify-center gap-2 px-6 py-3 bg-white/15 text-white font-semibold rounded-lg hover:bg-white/25 transition-colors text-sm border border-white/30 no-underline"
                            >
                                VER TENDENCIAS
                            </Link>
                        </div>
                    </div>
                </section>

            </main>
        </>
    );
}
