import "./styles.css"

export const metadata = { title: "ArchAI Studio", description: "Evidence-aware neural architecture research" }
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="en"><body>{children}</body></html> }
