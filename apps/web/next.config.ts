import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  productionBrowserSourceMaps: false,
  async headers() {
    const origins = [process.env.NEXT_PUBLIC_API_URL, process.env.NEXT_PUBLIC_SUPABASE_URL]
      .flatMap((value) => {
        try { return value ? [new URL(value).origin] : []; } catch { return []; }
      });
    const csp = [
      "default-src 'self'",
      "base-uri 'self'",
      "object-src 'none'",
      "frame-ancestors 'none'",
      "form-action 'self'",
      "script-src 'self' 'unsafe-inline' https://maps.googleapis.com https://maps.gstatic.com",
      "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
      "font-src 'self' https://fonts.gstatic.com",
      "worker-src 'self' blob:",
      "img-src 'self' data: blob: https://*.googleapis.com https://*.gstatic.com https://*.google.com",
      `connect-src 'self' ${origins.join(" ")} https://*.googleapis.com https://*.gstatic.com${process.env.NODE_ENV === "development" ? " http://localhost:* ws://localhost:*" : ""}`,
    ].join("; ");
    return [{ source: "/:path*", headers: [
      { key: "Content-Security-Policy", value: csp },
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "X-Frame-Options", value: "DENY" },
      // Google validates website-restricted Maps keys using the requesting origin.
      // Paths and query strings (including booking tokens) remain private cross-origin.
      { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
      { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(self)" },
    ] }];
  },
};

export default nextConfig;

