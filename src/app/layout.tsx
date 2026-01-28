import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Analytics } from "@vercel/analytics/react";
import { SpeedInsights } from "@vercel/speed-insights/next";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "ChivoCasa - Property Dashboard",
  description:
    "Dashboard de propiedades inmobiliarias en El Salvador. Encuentra casas y apartamentos en venta y alquiler.",
};

// 20260128 Cambio para usar Analitycs Vercel con ChatGPT
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es">
      <body className={inter.className}>
        {children}
		
        {/* Performance */}
        <SpeedInsights />

        {/* Analytics */}
        <Analytics />
		
      </body>
    </html>
  );
}
