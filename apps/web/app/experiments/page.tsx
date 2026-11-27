import type { Metadata } from "next"
import { Experiments } from "../screens/Experiments"

export const metadata: Metadata = { title: "Experiment History" }

export default function Page() {
  return <Experiments />
}
