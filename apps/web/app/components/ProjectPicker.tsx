"use client"
import { type ChangeEvent, type FormEvent, useEffect, useState } from "react"
import { usePoll } from "./usePoll"
import { postJson } from "../lib/api"
import { buildProjectRequest, defaultProjectForm, type ProjectForm } from "../lib/forms"
import { readSelectedProjectId, writeSelectedProjectId } from "../lib/project"
import type { ResearchProject } from "../lib/types"
import { Empty, Loaded } from "./Shell"

export function useSelectedProject() {
  const [projectId, setProjectId] = useState("")
  useEffect(() => { setProjectId(readSelectedProjectId()) }, [])
  const select = (id: string) => { writeSelectedProjectId(id); setProjectId(id) }
  return { projectId, select }
}

export function ProjectPicker() {
  const projects = usePoll<{ items: ResearchProject[] }>("/v1/projects")
  const { projectId, select } = useSelectedProject()
  const [form, setForm] = useState<ProjectForm>(defaultProjectForm)
  const [errors, setErrors] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState("")
  const onChange = (key: keyof ProjectForm) => (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setForm({ ...form, [key]: event.target.value })
  const onCreate = async (event: FormEvent) => {
    event.preventDefault()
    const built = buildProjectRequest(form)
    if (!built.ok) { setErrors(built.errors); return }
    setBusy(true); setErrors([]); setNotice("")
    const outcome = await postJson<ResearchProject>("/v1/projects", built.value)
    setBusy(false)
    if (!outcome.ok) { setErrors([`${outcome.status}: ${outcome.detail}`]); return }
    select(outcome.data.project_id)
    setForm(defaultProjectForm)
    setNotice(`Created ${outcome.data.name}.`)
    projects.refresh()
  }
  return <article className="panel" aria-labelledby="project-heading">
    <p className="eyebrow">RESEARCH PROJECT</p>
    <h3 id="project-heading">Create or select a project</h3>
    <p>E2E step 1 and later searches attach work to the selected project. Archived projects cannot accept new jobs.</p>
    {notice ? <p role="status">{notice}</p> : null}
    {errors.length ? <ul className="error-list">{errors.map((error) => <li key={error} className="error-text">{error}</li>)}</ul> : null}
    <form className="form" onSubmit={onCreate} aria-label="Create research project">
      <label>Name<input name="name" value={form.name} onChange={onChange("name")} required maxLength={128} /></label>
      <label>Task<input name="task" value={form.task} onChange={onChange("task")} required maxLength={128} /></label>
      <label>Description<textarea name="description" value={form.description} onChange={onChange("description")} maxLength={2000} rows={2} /></label>
      <button type="submit" disabled={busy}>{busy ? "Creating…" : "Create project"}</button>
    </form>
    <Loaded poll={projects} isEmpty={(data) => !data.items?.length} empty="No research projects yet.">
      {(data) => <ul className="project-list">{data.items.map((project) => <li key={project.project_id}>
        <button type="button" aria-pressed={projectId === project.project_id} onClick={() => select(project.project_id)} disabled={project.status !== "active"}>
          Select {project.name}
        </button>
        <span>{project.task} · {project.status}</span>
        {projectId === project.project_id ? <strong> selected</strong> : null}
      </li>)}</ul>}
    </Loaded>
  </article>
}

export function SelectedProjectLabel() {
  const { projectId } = useSelectedProject()
  const projects = usePoll<{ items: ResearchProject[] }>("/v1/projects", 0)
  const project = projects.data?.items.find((item) => item.project_id === projectId)
  if (!projectId) return <p className="muted">No project selected. Create one on the Research Dashboard.</p>
  if (!project) return <p>Selected project: <code>{projectId.slice(0, 8)}</code></p>
  return <p>Selected project: <strong>{project.name}</strong> <code>{project.project_id.slice(0, 8)}</code></p>
}
