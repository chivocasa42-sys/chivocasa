/**
 * Dynamic Open Graph Image Generator
 * 
 * Server-side generated OG image for social sharing.
 * Uses @vercel/og for edge-compatible image generation.
 */
import { ImageResponse } from 'next/og';

export const runtime = 'edge';

export const alt = 'ChivoCasa - Propiedades en El Salvador';
export const size = {
    width: 1200,
    height: 630,
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
                        marginBottom: 40,
                    }}
                >
                    <div
                        style={{
                            fontSize: 72,
                            fontWeight: 800,
                            color: '#ffffff',
                            letterSpacing: '-0.02em',
                        }}
                    >
                        Chivo
                        <span style={{ color: '#38bdf8' }}>Casa</span>
                    </div>
                </div>

                {/* Tagline */}
                <div
                    style={{
                        fontSize: 32,
                        color: '#94a3b8',
                        marginBottom: 60,
                    }}
                >
                    Propiedades en El Salvador
                </div>

                {/* Stats Bar */}
                <div
                    style={{
                        display: 'flex',
                        gap: 60,
                    }}
                >
                    <div
                        style={{
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                        }}
                    >
                        <div style={{ fontSize: 48, fontWeight: 700, color: '#38bdf8' }}>
                            2,600+
                        </div>
                        <div style={{ fontSize: 18, color: '#64748b' }}>
                            Propiedades
                        </div>
                    </div>
                    <div
                        style={{
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                        }}
                    >
                        <div style={{ fontSize: 48, fontWeight: 700, color: '#38bdf8' }}>
                            14
                        </div>
                        <div style={{ fontSize: 18, color: '#64748b' }}>
                            Departamentos
                        </div>
                    </div>
                    <div
                        style={{
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                        }}
                    >
                        <div style={{ fontSize: 48, fontWeight: 700, color: '#38bdf8' }}>
                            📈
                        </div>
                        <div style={{ fontSize: 18, color: '#64748b' }}>
                            Actualizado diario
                        </div>
                    </div>
                </div>

                {/* Footer */}
                <div
                    style={{
                        position: 'absolute',
                        bottom: 40,
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        color: '#475569',
                        fontSize: 16,
                    }}
                >
                    chivocasa.com
                </div>
            </div>
        ),
        {
            ...size,
        }
    );
}
