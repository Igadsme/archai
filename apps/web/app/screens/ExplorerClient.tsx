"use client"
import dynamic from "next/dynamic"
import { Icon } from "../studio/Icon"

// The workbench restores tabs and panel sizes from localStorage and measures the canvas, so it renders client-side only.
export const ExplorerClient = dynamic(() => import("./Explorer").then((module) => module.Explorer), {
  ssr: false,
  loading: () => <div className="workspace-loading" role="status"><Icon name="explorer" /> Loading architecture workbench…</div>,
})
