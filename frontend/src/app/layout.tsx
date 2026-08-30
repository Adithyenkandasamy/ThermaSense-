import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ThermaSense",
  description:
    "Geospatial Thermal Intelligence — satellite thermal anomaly detection and investigation platform powered by NASA FIRMS data.",
  icons: {
    icon: [
      { url: "/favicon.png", type: "image/png", sizes: "256x256" },
      { url: "/favicon.ico", type: "image/x-icon" },
    ],
    shortcut: "/favicon.png",
    apple: "/favicon.png",
  },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <head>
        <link rel="icon" href="/favicon.png" type="image/png" sizes="256x256" />
        <link rel="shortcut icon" href="/favicon.ico" />
        <link rel="apple-touch-icon" href="/favicon.png" />
      </head>
      <body style={{ fontFamily: "Inter, 'Segoe UI', sans-serif" }}>
        {children}
      </body>
    </html>
  );
}
