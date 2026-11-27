import type { Metadata } from "next"
import { ExplorerClient } from "../screens/ExplorerClient"

export const metadata: Metadata = { title: "Neural Architecture Explorer" }

export default function Page() {
  return <ExplorerClient />
}
