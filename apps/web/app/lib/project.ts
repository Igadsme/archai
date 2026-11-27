"use client"

export const PROJECT_STORAGE_KEY = "archai.projectId"
export const PROJECT_EVENT = "archai:project"

export function readSelectedProjectId(): string {
  if (typeof window === "undefined") return ""
  return window.sessionStorage.getItem(PROJECT_STORAGE_KEY) ?? ""
}

export function writeSelectedProjectId(projectId: string): void {
  if (typeof window === "undefined") return
  if (projectId) window.sessionStorage.setItem(PROJECT_STORAGE_KEY, projectId)
  else window.sessionStorage.removeItem(PROJECT_STORAGE_KEY)
  window.dispatchEvent(new Event(PROJECT_EVENT))
}
