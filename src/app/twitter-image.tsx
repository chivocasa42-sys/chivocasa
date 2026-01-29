/**
 * Dynamic Twitter Image Generator
 * 
 * Server-side generated Twitter card image.
 * Reuses the OG image structure with Twitter-optimized dimensions.
 */
import { ImageResponse } from 'next/og';

export const runtime = 'edge';

export const alt = 'sivarcasas - Propiedades en El Salvador';
export const size = {
    width: 1200,
    height: 600,
};
export const contentType = 'image/png';

export default async function Image() {
    return new ImageResponse(
        (
            <div
                style={{
                    height: '100%',
                    width: '100%',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #334155 100%)',
                    fontFamily: 'Inter, system-ui, sans-serif',
                }}
            >
                {/* Logo/Brand */}
                <div
                    style={{
                        display: 'flex',
                        alignItems: 'center',
                        marginBottom: 30,
                    }}
                >
                    <div
                        style={{
                            fontSize: 64,
                            fontWeight: 800,
                            color: '#ffffff',
                            letterSpacing: '-0.02em',
                        }}
                    >
                        Sivar
                        <span style={{ color: '#38bdf8' }}>Casas</span>
                    </div>
                </div>

                {/* Tagline */}
                <div
                    style={{
                        fontSize: 28,
                        color: '#94a3b8',
                        marginBottom: 40,
                    }}
                >
                    Encuentra tu próximo hogar en El Salvador
                </div>

                {/* Stats Bar */}
                <div
                    style={{
                        display: 'flex',
                        gap: 50,
                    }}
                >
                    <div
                        style={{
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                        }}
                    >
                        <div style={{ fontSize: 40, fontWeight: 700, color: '#38bdf8' }}>
                            Venta
                        </div>
                        <div style={{ fontSize: 16, color: '#64748b' }}>
                            Casas & Apartamentos
                        </div>
                    </div>
                    <div
                        style={{
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                        }}
                    >
                        <div style={{ fontSize: 40, fontWeight: 700, color: '#38bdf8' }}>
                            Renta
                        </div>
                        <div style={{ fontSize: 16, color: '#64748b' }}>
                            Mensual
                        </div>
                    </div>
                </div>

                {/* Footer */}
                <div
                    style={{
                        position: 'absolute',
                        bottom: 30,
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        color: '#475569',
                        fontSize: 14,
                    }}
                >
                    🏠 sivarcasas.com
                </div>
            </div>
        ),
        {
            ...size,
        }
    );
}
