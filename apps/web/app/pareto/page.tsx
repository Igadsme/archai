import type { Metadata } from "next"
import { Pareto } from "../screens/Pareto"

export const metadata: Metadata = { title: "Pareto Optimization Explorer" }

export default function Page() {
  return <Pareto />
}
