import type { IconName } from "./Icon"

export type View = "overview" | "explorer" | "generator" | "search" | "training" | "pareto" | "benchmarks" | "experiments" | "registry" | "system"

export type Screen = { id: View; href: string; label: string; title: string; detail: string; icon: IconName; section?: "EXECUTION" | "EVIDENCE" | "PLATFORM" }

/** The ten ArchAI Studio V3 screens, in sidebar order. */
export const SCREENS: readonly Screen[] = [
  { id: "overview", href: "/", label: "Research Overview", title: "Research Overview", detail: "Live research summary from the API", icon: "overview" },
  { id: "explorer", href: "/explorer", label: "Architecture Explorer", title: "Neural Architecture Explorer", detail: "Inspect validated computation graphs", icon: "explorer" },
  { id: "generator", href: "/generator", label: "Generator", title: "Architecture Generator", detail: "Sample from the trained generator checkpoint", icon: "generator" },
  { id: "search", href: "/search", label: "Search Laboratory", title: "Autonomous Search Laboratory", detail: "Launch and monitor budgeted searches", icon: "search", section: "EXECUTION" },
  { id: "training", href: "/training", label: "Training", title: "Training and GPU Monitoring", detail: "Queue worker training jobs, read measured curves", icon: "training" },
  { id: "pareto", href: "/pareto", label: "Pareto Explorer", title: "Pareto Optimization Explorer", detail: "Measured accuracy vs. parameter fronts", icon: "pareto" },
  { id: "benchmarks", href: "/benchmarks", label: "Benchmarks", title: "Benchmark Comparison", detail: "Policies, architectures and result sets", icon: "benchmarks", section: "EVIDENCE" },
  { id: "experiments", href: "/experiments", label: "Experiments", title: "Experiment History", detail: "Job and experiment records with diagnostics", icon: "experiments" },
  { id: "registry", href: "/registry", label: "Model Registry", title: "Model Registry", detail: "Architectures and checksum-verified checkpoints", icon: "registry" },
  { id: "system", href: "/system", label: "System Settings", title: "System Administration", detail: "Readiness, queue, workers, datasets, audit", icon: "system", section: "PLATFORM" },
]

export function screenForPath(pathname: string | null): Screen {
  const path = (pathname ?? "/").replace(/\/+$/, "") || "/"
  return SCREENS.find((screen) => screen.href === path) ?? SCREENS.find((screen) => screen.href !== "/" && path.startsWith(`${screen.href}/`)) ?? SCREENS[0]
}

export const hrefFor = (view: View): string => SCREENS.find((screen) => screen.id === view)?.href ?? "/"

/** Routes of the previous Studio, redirected to their V3 screen. */
export const LEGACY_REDIRECTS: readonly { source: string; destination: string }[] = [
  { source: "/compare", destination: "/benchmarks" },
  { source: "/results", destination: "/benchmarks" },
  { source: "/models", destination: "/registry" },
  { source: "/admin", destination: "/system" },
]
