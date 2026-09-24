import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CaféIA | Análisis de hojas de café",
  description: "Prototipo académico para clasificar tres condiciones en hojas de café.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}
