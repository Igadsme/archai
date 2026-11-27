import { readFileSync } from "node:fs"

const apiBase = process.env.NEXT_PUBLIC_ARCHAI_API_URL || "http://127.0.0.1:8000"
const apiOrigin = new URL(apiBase).origin
const { version } = JSON.parse(readFileSync(new URL("./package.json", import.meta.url), "utf8"))

// Next.js injects inline bootstrap scripts, so script-src needs 'unsafe-inline' without a nonce setup.
export const contentSecurityPolicy = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self'",
  `connect-src 'self' ${apiOrigin}`,
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "object-src 'none'",
].join("; ")

const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
]

/** Routes of the pre-V3 Studio; kept as redirects so bookmarks keep working (mirrors LEGACY_REDIRECTS). */
export const legacyRedirects = [
  { source: "/compare", destination: "/benchmarks" },
  { source: "/results", destination: "/benchmarks" },
  { source: "/models", destination: "/registry" },
  { source: "/admin", destination: "/system" },
]

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  env: { NEXT_PUBLIC_STUDIO_VERSION: version },
  // The Docker image sets NEXT_OUTPUT=standalone; Vercel and `next start` use the default output.
  output: process.env.NEXT_OUTPUT === "standalone" ? "standalone" : undefined,
  async headers() {
    const headers = process.env.NODE_ENV === "production"
      ? [...securityHeaders, { key: "Content-Security-Policy", value: contentSecurityPolicy }]
      : securityHeaders
    return [{ source: "/:path*", headers }]
  },
  async redirects() {
    return legacyRedirects.map((redirect) => ({ ...redirect, permanent: false }))
  },
}

export default nextConfig
