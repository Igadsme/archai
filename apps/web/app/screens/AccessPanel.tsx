"use client"
import { useState } from "react"
import { items, usePoll } from "../components/usePoll"
import { describeFailure, request } from "../lib/api"
import type { ApiKeyItem, IssuedApiKey, UserItem, WhoAmI } from "../lib/types"
import { Icon } from "../studio/Icon"
import { ErrorList, Loaded, Notice, Panel, shortId, Status, Unavailable } from "../studio/ui"

export const SCOPE_CHOICES = ["read", "write", "admin"] as const
export type ScopeChoice = (typeof SCOPE_CHOICES)[number]

/** One-line description of the current credential, from GET /v1/auth/whoami only. */
export function accessSummary(whoami: WhoAmI | null): { label: string; tone: "teal" | "amber" | "red" | "gray"; canAdmin: boolean } {
  if (!whoami) return { label: "UNKNOWN", tone: "gray", canAdmin: false }
  const scopes = whoami.principal.scopes
  const canAdmin = scopes.includes("admin")
  if (!whoami.auth_enabled) return { label: "OPEN MODE · NO KEYS CONFIGURED", tone: "amber", canAdmin }
  if (!whoami.authenticated) return { label: "NO KEY ENTERED", tone: "red", canAdmin: false }
  const who = whoami.principal.kind === "bootstrap" ? "BOOTSTRAP KEY" : `${whoami.principal.email ?? "user"} · ${whoami.principal.key_prefix ?? ""}`
  return { label: `${who} · ${scopes.join("+").toUpperCase()}`, tone: "teal", canAdmin }
}

export function AccessPanel() {
  const whoami = usePoll<WhoAmI>("/v1/auth/whoami", 15_000)
  const summary = accessSummary(whoami.data)
  const users = usePoll<{ items: UserItem[] }>(summary.canAdmin ? "/v1/users" : null, 15_000)
  const keys = usePoll<{ items: ApiKeyItem[] }>(summary.canAdmin ? "/v1/api-keys" : null, 15_000)
  const [errors, setErrors] = useState<string[]>([])
  const [notice, setNotice] = useState("")
  const [issued, setIssued] = useState<IssuedApiKey | null>(null)
  const [email, setEmail] = useState("")
  const [role, setRole] = useState<"member" | "admin">("member")
  const [keyUser, setKeyUser] = useState("")
  const [keyName, setKeyName] = useState("")
  const [scopes, setScopes] = useState<ScopeChoice[]>(["read", "write"])
  const [expires, setExpires] = useState("")
  const [busy, setBusy] = useState(false)
  const userList = items(users.data)
  const emailOf = (userId: string) => userList.find((user) => user.user_id === userId)?.email ?? shortId(userId, 8)

  const act = async <T,>(path: string, body: unknown, method: "POST" | "PATCH" = "POST"): Promise<T | null> => {
    setBusy(true); setErrors([]); setNotice("")
    const result = await request<T>(path, { method, body })
    setBusy(false)
    if (!result.ok) { setErrors([describeFailure(result)]); return null }
    users.refresh(); keys.refresh(); whoami.refresh()
    return result.data
  }
  const createUser = async () => {
    const user = await act<UserItem>("/v1/users", { email, role })
    if (user) { setNotice(`Created user ${user.email}.`); setEmail(""); setKeyUser(user.user_id) }
  }
  const createKey = async () => {
    const days = expires.trim() ? Number(expires) : null
    if (days !== null && (!Number.isInteger(days) || days < 1)) { setErrors(["Expiry must be a whole number of days."]); return }
    const key = await act<IssuedApiKey>("/v1/api-keys", { user_id: keyUser, name: keyName, scopes, expires_in_days: days })
    if (key) { setIssued(key); setKeyName("") }
  }
  const rotate = async (key: ApiKeyItem) => { const next = await act<IssuedApiKey>(`/v1/api-keys/${key.credential_id}/rotate`, {}); if (next) setIssued(next) }
  const revoke = async (key: ApiKeyItem) => { if (await act(`/v1/api-keys/${key.credential_id}/revoke`, {})) setNotice(`Revoked ${key.key_prefix}.`) }
  const toggleUser = async (user: UserItem) => { if (await act(`/v1/users/${user.user_id}`, { disabled: user.active }, "PATCH")) setNotice(`${user.email} ${user.active ? "disabled" : "re-enabled"}.`) }

  return <Panel title="Users & API keys" meta="/v1/users · /v1/api-keys" className="span-all">
    <div className="setting-list">
      <div><span><b>Current credential</b><small>From /v1/auth/whoami. Keys are stored as SHA-256 digests; secrets are shown once.</small></span><Status tone={summary.tone}>{summary.label}</Status></div>
    </div>
    {!whoami.data ? <Loaded poll={whoami} label="identity">{() => null}</Loaded>
      : !summary.canAdmin ? <Unavailable feature="user and API-key management" reason={whoami.data.auth_enabled ? "Managing users and keys needs an admin-scoped key. Enter one in the sidebar (API KEY)." : "Open mode grants admin to everyone; create an admin user and key below to turn authentication on."} />
      : null}
    {summary.canAdmin ? <>
      <ErrorList errors={errors} /><Notice>{notice}</Notice>
      {issued ? <div className="system-alert" role="alert"><Icon name="alert" /><span>New key for <b>{emailOf(issued.user_id)}</b> ({issued.scopes.join("+")}). {issued.secret_notice}<br /><code className="secret-value" aria-label="New API key secret">{issued.secret}</code></span>
        <button className="button compact" onClick={() => { void navigator.clipboard?.writeText(issued.secret); setNotice("Copied the new key.") }}>Copy</button><button className="button compact" onClick={() => setIssued(null)}>Dismiss</button></div> : null}
      <div className="access-forms">
        <form onSubmit={(event) => { event.preventDefault(); void createUser() }} aria-label="Create user">
          <label className="field"><span>Email</span><input value={email} onChange={(event) => setEmail(event.target.value)} placeholder="researcher@example.org" required /></label>
          <label className="field"><span>Role</span><select value={role} onChange={(event) => setRole(event.target.value as "member" | "admin")}><option value="member">member</option><option value="admin">admin</option></select></label>
          <button className="button" type="submit" disabled={busy || !email.trim()}>Create user</button>
        </form>
        <form onSubmit={(event) => { event.preventDefault(); void createKey() }} aria-label="Issue API key">
          <label className="field"><span>Owner</span><select value={keyUser} onChange={(event) => setKeyUser(event.target.value)} required><option value="">Select a user</option>{userList.filter((user) => user.active).map((user) => <option key={user.user_id} value={user.user_id}>{user.email} ({user.role})</option>)}</select></label>
          <label className="field"><span>Key name</span><input value={keyName} onChange={(event) => setKeyName(event.target.value)} placeholder="laptop, ci, worker…" required /></label>
          <fieldset className="field scope-choices"><legend>Scopes</legend>{SCOPE_CHOICES.map((scope) => <label key={scope}><input type="checkbox" checked={scopes.includes(scope)} onChange={(event) => setScopes(event.target.checked ? [...scopes, scope] : scopes.filter((value) => value !== scope))} />{scope}</label>)}</fieldset>
          <label className="field"><span>Expires in (days, optional)</span><input inputMode="numeric" value={expires} onChange={(event) => setExpires(event.target.value)} placeholder="never" /></label>
          <button className="button primary" type="submit" disabled={busy || !keyUser || !keyName.trim() || scopes.length === 0}>Issue key</button>
        </form>
      </div>
      <Loaded poll={users} label="users" isEmpty={(data) => data.items.length === 0} empty="No user accounts yet.">{(data) => <div className="table-wrap"><table aria-label="Users"><thead><tr><th>EMAIL</th><th>ROLE</th><th>ACTIVE KEYS</th><th>CREATED (UTC)</th><th>STATE</th><th /></tr></thead><tbody>
        {data.items.map((user) => <tr key={user.user_id}><td>{user.email}</td><td>{user.role}</td><td className="mono">{user.active_keys ?? 0}</td><td className="mono">{user.created_at.replace("T", " ").slice(0, 19)}</td>
          <td><Status tone={user.active ? "teal" : "gray"}>{user.active ? "ACTIVE" : "DISABLED"}</Status></td><td><button className="button compact" disabled={busy} onClick={() => void toggleUser(user)}>{user.active ? "Disable" : "Enable"}</button></td></tr>)}
      </tbody></table></div>}</Loaded>
      <Loaded poll={keys} label="API keys" isEmpty={(data) => data.items.length === 0} empty="No managed keys yet.">{(data) => <div className="table-wrap"><table aria-label="API keys"><thead><tr><th>KEY</th><th>NAME</th><th>OWNER</th><th>SCOPES</th><th>LAST USED (UTC)</th><th>EXPIRES</th><th>STATE</th><th /></tr></thead><tbody>
        {data.items.map((key) => <tr key={key.credential_id}><td><code>{key.key_prefix}…</code></td><td>{key.name}</td><td>{emailOf(key.user_id)}</td><td className="mono">{key.scopes.join("+")}</td>
          <td className="mono">{key.last_used_at?.replace("T", " ").slice(0, 19) ?? "never"}</td><td className="mono">{key.expires_at?.slice(0, 10) ?? "never"}</td>
          <td><Status tone={key.state === "active" ? "teal" : key.state === "expired" ? "amber" : "gray"}>{key.state.toUpperCase()}</Status></td>
          <td>{key.state === "revoked" ? null : <span className="inspector-actions"><button className="button compact" disabled={busy} onClick={() => void rotate(key)}>Rotate</button><button className="button compact" disabled={busy} onClick={() => void revoke(key)}>Revoke</button></span>}</td></tr>)}
      </tbody></table></div>}</Loaded>
    </> : null}
  </Panel>
}
