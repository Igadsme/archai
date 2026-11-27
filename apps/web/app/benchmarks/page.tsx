import type { Metadata } from "next"
import { Benchmarks } from "../screens/Benchmarks"

export const metadata: Metadata = { title: "Benchmark Comparison" }

export default function Page() {
  return <Benchmarks />
}
