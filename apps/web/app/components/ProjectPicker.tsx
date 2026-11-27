"use client"
import { type ChangeEvent, type FormEvent, useEffect, useState } from "react"
import { items, usePoll } from "./usePoll"
import { describeFailure, postJson } from "../lib/api"
import { ConstraintFields } from "./ConstraintFields"
import { buildProjectRequest, defaultProjectForm, type ProjectForm } from "../lib/forms"
import { PROJECT_EVENT, readSelectedProjectId, writeSelectedProjectId } from "../lib/project"
import type { ResearchProject } from "../lib/types"
import { itemsResponse } from "../lib/validators"
import { ErrorList, Loaded, Notice, Panel, Status } from "../studio/ui"

export function useSelectedProject() {
  const [projectId, setProjectId] = useState("")
  useEffect(() => {
    const sync = () => setProjectId(readSelectedProjectId())
    sync()
    window.addEventListener(PROJECT_EVENT, sync)
    return () => window.removeEventListener(PROJECT_EVENT, sync)
  }, [])
  const select = (id: string) => { writeSelectedProjectId(id); setProjectId(id) }
  return { projectId, select }
}

export function ProjectPicker() {
  const projects = usePoll<{ items: ResearchProject[] }>("/v1/projects", 15_000, itemsResponse)
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
    if (!outcome.ok) { setErrors([describeFailure(outcome)]); return }
    select(outcome.data.project_id)
    setForm(defaultProjectForm)
    setNotice(`Created ${outcome.data.name}.`)
    projects.refresh()
  }
  return <Panel title="Research project" meta={`${items(projects.data).length} RECORDS`} className="project-panel">
    <div className="form-body">
      <p className="panel-note">Searches and generation requests attach to the selected project and inherit its constraints. Archived projects cannot accept new jobs.</p>
      <Notice>{notice}</Notice>
      <ErrorList errors={errors} />
      <form className="stacked-form" onSubmit={onCreate} aria-label="Create research project">
        <div className="form-grid">
          <label className="field"><span>Name</span><input name="name" value={form.name} onChange={onChange("name")} required maxLength={128} /></label>
          <label className="field"><span>Task</span><input name="task" value={form.task} onChange={onChange("task")} required maxLength={128} /></label>
        </div>
        <label className="field"><span>Description</span><textarea name="description" value={form.description} onChange={onChange("description")} maxLength={2000} rows={2} /></label>
        <details className="constraint-details"><summary>Project constraints (optional)</summary><div className="form-grid"><ConstraintFields form={form} onChange={onChange} /></div></details>
        <button className="button primary" type="submit" disabled={busy}>{busy ? "Creating…" : "Create project"}</button>
      </form>
    </div>
    <Loaded poll={projects} label="projects" isEmpty={(data) => !data.items?.length} empty="No research projects yet.">
      {(data) => <div className="project-list">{data.items.map((project) => <div key={project.project_id} className={projectId === project.project_id ? "active" : ""}>
        <span><b>{project.name}</b><small>{project.task} · {project.project_id.slice(0, 8)}</small></span>
        <Status tone={project.status === "active" ? "teal" : "gray"}>{project.status.toUpperCase()}</Status>
        <button type="button" className="button compact" aria-label={`Select ${project.name}`} aria-pressed={projectId === project.project_id} onClick={() => select(project.project_id)} disabled={project.status !== "active"}>
          {projectId === project.project_id ? "Selected" : `Select ${project.name}`}
        </button>
      </div>)}</div>}
    </Loaded>
  </Panel>
}

export function SelectedProjectLabel() {
  const { projectId } = useSelectedProject()
  const projects = usePoll<{ items: ResearchProject[] }>("/v1/projects", 0, itemsResponse)
  const project = projects.data?.items.find((item) => item.project_id === projectId)
  if (!projectId) return <p className="panel-note">No project selected — choose one in the sidebar or on Research Overview.</p>
  return <p className="panel-note">Project: <b>{project?.name ?? projectId.slice(0, 8)}</b> <code>{projectId.slice(0, 8)}</code></p>
}
