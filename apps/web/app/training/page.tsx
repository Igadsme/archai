import type { Metadata } from "next"
import { Training } from "../screens/Training"

export const metadata: Metadata = { title: "Training & GPU Monitoring" }

export default function Page() {
  return <Training />
}
