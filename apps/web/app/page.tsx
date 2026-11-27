import type { Metadata } from "next"
import { Overview } from "./screens/Overview"

export const metadata: Metadata = { title: "Research Overview" }

export default function Page() {
  return <Overview />
}
