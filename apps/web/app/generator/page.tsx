import type { Metadata } from "next"
import { Generator } from "../screens/Generator"

export const metadata: Metadata = { title: "Architecture Generator" }

export default function Page() {
  return <Generator />
}
