import "./styles.css"
import { Shell } from "./components/Shell"

export const metadata = { title: "ArchAI Studio", description: "Evidence-aware neural architecture research" }
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body><Shell>{children}</Shell></body></html>
}
