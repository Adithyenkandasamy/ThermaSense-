import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // ── Turbopack configuration for Next.js 16 ─────────────────────────
  turbopack: {},

  // ── Security & CORS headers ────────────────────────────────────────
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          {
            key: "X-Content-Type-Options",
            value: "nosniff",
          },
          {
            key: "X-Frame-Options",
            value: "DENY",
          },
          {
            key: "Referrer-Policy",
            value: "strict-origin-when-cross-origin",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
