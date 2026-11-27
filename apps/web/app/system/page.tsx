import type { Metadata } from "next"
import { SystemAdmin } from "../screens/System"

export const metadata: Metadata = { title: "System Administration" }

export default function Page() {
  return <SystemAdmin />
}
