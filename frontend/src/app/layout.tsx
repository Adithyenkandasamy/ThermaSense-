import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "ThermaSense — Geospatial Thermal Intelligence",
  description:
    "Satellite thermal anomaly detection and investigation platform. Powered by NASA FIRMS data from NOAA-20 and NOAA-21 VIIRS instruments.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${inter.variable} h-full antialiased`}>
      <body className="min-h-full bg-slate-950 text-slate-200 font-[family-name:var(--font-inter)]">
        {children}
      </body>
    </html>
  );
}
