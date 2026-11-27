import type { Metadata } from "next"
import { SearchLab } from "../screens/SearchLab"

export const metadata: Metadata = { title: "Autonomous Search Laboratory" }

export default function Page() {
  return <SearchLab />
}
