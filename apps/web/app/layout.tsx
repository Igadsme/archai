import type { Metadata, Viewport } from "next"
import { Inter, JetBrains_Mono } from "next/font/google"
import "./studio/preflight.css"
import "./studio/figma-v3.css"
import "./studio/studio.css"
import { StudioShell } from "./studio/StudioShell"

// next/font self-hosts the files at build time, so the CSP keeps font-src 'self'.
const inter = Inter({ subsets: ["latin"], weight: ["400", "500", "600"], variable: "--font-inter", display: "swap" })
const mono = JetBrains_Mono({ subsets: ["latin"], weight: ["400", "500", "600"], variable: "--font-jetbrains-mono", display: "swap" })

export const metadata: Metadata = { title: { default: "ArchAI Studio", template: "%s · ArchAI Studio" }, description: "Evidence-aware neural architecture research" }
export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#090d11" }

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" className={`${inter.variable} ${mono.variable}`}><body><StudioShell>{children}</StudioShell></body></html>
}
