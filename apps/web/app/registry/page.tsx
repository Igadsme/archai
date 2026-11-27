import type { Metadata } from "next"
import { Registry } from "../screens/Registry"

export const metadata: Metadata = { title: "Model Registry" }

export default function Page() {
  return <Registry />
}
