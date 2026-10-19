import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CaféIA | Análisis de hojas de café",
  description: "Analiza fotografías de hojas de café y compáralas con las categorías sana, roya y daño por ácaro rojo.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}
