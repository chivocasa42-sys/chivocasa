import Image from 'next/image';
import Link from 'next/link';

interface HeroSectionProps {
    variant?: 'cta';
}

export default function HeroSection({ variant = 'cta' }: HeroSectionProps) {
    return (
        <section className={`hero-search${variant === 'cta' ? ' hero-search--cta' : ''}`}>
            <Image
                src="/jardin-ca-01.webp"
                alt=""
                aria-hidden="true"
                fill
                priority
                fetchPriority="high"
                sizes="100vw"
                className="hero-search-bg"
            />
            <div className="hero-search-overlay" />

            <div className="hero-search-content">
                <h1 className="hero-search-title">
                    La fuente de datos inmobiliarios #1 de El Salvador
                </h1>

                <div className="hero-search-actions">
                    <Link href="/departamentos" className="hero-search-cta hero-search-cta--secondary">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                            <path d="M8 5H5V8" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
                            <path d="M16 19H19V16" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
                            <path d="M19 8V5H16" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
                            <path d="M5 16V19H8" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
                            <path d="M8 8L16 16" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
                            <path d="M16 8L8 16" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
                        </svg>
                        <span>Comparar zonas</span>
                    </Link>

                    <Link href="/explorar-por-ubicacion" className="hero-search-cta hero-search-cta--primary">
                        <span>Explorar mapa</span>
                        <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
                            <path d="M4.5 9H13.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
                            <path d="M9.75 5.25L13.5 9L9.75 12.75" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                    </Link>
                </div>

                <p className="hero-search-slogan">
                    Más casa por tu dinero.
                </p>
            </div>
        </section>
    );
}
