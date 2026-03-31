import Link from 'next/link';
import SectionHeader from '@/components/SectionHeader';

function TrendsIcon() {
    return (
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M4 16L9 11L13 15L20 8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M16 8H20V12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
    );
}

function CalculatorIcon() {
    return (
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <rect x="5" y="3" width="14" height="18" rx="3" stroke="currentColor" strokeWidth="2" />
            <path d="M8 7H16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            <path d="M8 11H10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            <path d="M14 11H16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            <path d="M8 15H10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            <path d="M14 15H16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
    );
}

function CompareIcon() {
    return (
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M8 5H5V8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M16 19H19V16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M19 8V5H16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M5 16V19H8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M8 8L16 16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            <path d="M16 8L8 16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
    );
}

function MapIcon() {
    return (
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M12 21C15.5 17 18 14.1 18 10.5C18 6.9 15.3 4 12 4C8.7 4 6 6.9 6 10.5C6 14.1 8.5 17 12 21Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            <circle cx="12" cy="10" r="2.5" stroke="currentColor" strokeWidth="2" />
        </svg>
    );
}

const TOOLS = [
    {
        href: '/departamentos',
        badge: 'Analisis',
        title: 'Comparador por Departamento',
        description: 'Compara zonas lado a lado con precios medios, rangos y volumen de oferta activa.',
        cta: 'Comparar departamentos',
        accent: '#d49434',
        textAccent: '#8a5a10',
        chipBg: 'rgba(212, 148, 52, 0.12)',
        iconBg: 'rgba(212, 148, 52, 0.12)',
        iconBorder: 'rgba(212, 148, 52, 0.18)',
        icon: <CompareIcon />,
    },
    {
        href: '/tendencias',
        badge: 'Dashboard',
        title: 'Tendencias del Mercado',
        description: 'Graficos de evolucion mensual de precios, rentas y actividad por departamento.',
        cta: 'Ver tendencias',
        accent: '#3f7fe0',
        textAccent: '#2557a8',
        chipBg: 'rgba(63, 127, 224, 0.12)',
        iconBg: 'rgba(63, 127, 224, 0.12)',
        iconBorder: 'rgba(63, 127, 224, 0.18)',
        icon: <TrendsIcon />,
    },
    {
        href: '/valuador-de-inmuebles',
        badge: 'Herramienta',
        title: 'Valuador de Propiedades',
        description: 'Estima el valor de cualquier propiedad con comparables y datos reales del mercado.',
        cta: 'Abrir valuador',
        accent: '#26b786',
        textAccent: '#0f7d59',
        chipBg: 'rgba(38, 183, 134, 0.12)',
        iconBg: 'rgba(38, 183, 134, 0.12)',
        iconBorder: 'rgba(38, 183, 134, 0.18)',
        icon: <CalculatorIcon />,
    },
    {
        href: '/explorar-por-ubicacion',
        badge: 'Mapa',
        title: 'Mapa de Precios',
        description: 'Explora ubicaciones, propiedades cercanas y senales de precio en el mapa interactivo.',
        cta: 'Explorar mapa',
        accent: '#e66774',
        textAccent: '#b33d4a',
        chipBg: 'rgba(230, 103, 116, 0.12)',
        iconBg: 'rgba(230, 103, 116, 0.12)',
        iconBorder: 'rgba(230, 103, 116, 0.18)',
        icon: <MapIcon />,
    },
];

export default function HomeToolsSection() {
    return (
        <section className="mb-14">
            <SectionHeader
                title={['Herramientas que nos', 'hacen diferentes']}
                subtitle="Funcionalidades que ningun otro portal inmobiliario en El Salvador ofrece"
            />

            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-5">
                {TOOLS.map((tool) => (
                    <Link
                        key={tool.href}
                        href={tool.href}
                        className="card-float no-underline p-6 md:p-7 min-h-[280px] relative overflow-hidden group"
                    >
                        <div
                            className="absolute inset-x-0 top-0 h-1"
                            style={{ background: `linear-gradient(90deg, ${tool.accent} 0%, rgba(255,255,255,0) 100%)` }}
                        />
                        <div
                            className="absolute -right-10 -top-12 h-28 w-28 rounded-full blur-3xl opacity-20"
                            style={{ backgroundColor: tool.accent }}
                        />

                        <div className="relative flex h-full flex-col">
                            <span
                                className="inline-flex w-fit items-center rounded-full px-3 py-1 text-xs font-semibold"
                                style={{ backgroundColor: tool.chipBg, color: tool.textAccent }}
                            >
                                {tool.badge}
                            </span>

                            <div
                                className="mt-4 h-12 w-12 rounded-2xl border flex items-center justify-center"
                                style={{
                                    backgroundColor: tool.iconBg,
                                    borderColor: tool.iconBorder,
                                    color: tool.accent,
                                }}
                            >
                                {tool.icon}
                            </div>

                            <h3 className="mt-5 text-[1.55rem] leading-tight font-black tracking-tight text-[var(--text-primary)]">
                                {tool.title}
                            </h3>

                            <p className="mt-3 text-base leading-7 text-[var(--text-muted)]">
                                {tool.description}
                            </p>

                            <div
                                className="mt-auto pt-6 inline-flex items-center gap-2 text-sm font-semibold transition-transform group-hover:translate-x-1"
                                style={{ color: tool.textAccent }}
                            >
                                <span>{tool.cta}</span>
                                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                                    <path d="M3 8H13" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
                                    <path d="M9.5 4.5L13 8L9.5 11.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
                                </svg>
                            </div>
                        </div>
                    </Link>
                ))}
            </div>
        </section>
    );
}
