import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

// INICIO Agregado para el Analitycs MAHR 20260128
import { Analytics } from "@vercel/analytics/react";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body>
        {children}
        <Analytics />
      </body>
    </html>
  );
}
// FIN Agregado MAHR 20260128

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "ChivoCasa - Property Dashboard",
  description: "Dashboard de propiedades inmobiliarias en El Salvador. Encuentra casas y apartamentos en venta y alquiler.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es">
      <body className={inter.className}>
        {children}
      </body>
    </html>
  );
}
