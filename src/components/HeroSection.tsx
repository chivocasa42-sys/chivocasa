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
                    <Link href="/tendencias" className="hero-search-cta hero-search-cta--primary">
                        <span>Ver Tendencias</span>
                        <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
                            <path d="M4.5 9H13.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
                            <path d="M9.75 5.25L13.5 9L9.75 12.75" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                    </Link>

                    <Link href="/valuador-de-inmuebles" className="hero-search-cta hero-search-cta--secondary">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                            <path d="M9 7H15M15 17V14M12 17H12.01M9 17H9.01M9 14H9.01M12 14H12.01M15 11H15.01M12 11H12.01M9 11H9.01M7 21H17A2 2 0 0 0 19 19V5A2 2 0 0 0 17 3H7A2 2 0 0 0 5 5V19A2 2 0 0 0 7 21Z" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                        <span>Valuar Propiedad</span>
                    </Link>
                </div>

                <p className="hero-search-slogan">
                    Mas casa por tu dinero.
                </p>
            </div>
        </section>
    );
}
