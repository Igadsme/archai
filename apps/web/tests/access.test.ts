import { describe, expect, it } from "vitest"
import type { WhoAmI } from "../app/lib/types"
import { accessSummary } from "../app/screens/AccessPanel"

const principal = (overrides: Partial<WhoAmI["principal"]> = {}): WhoAmI["principal"] => ({ kind: "anonymous", scopes: [], user_id: null, email: null, credential_id: null, key_prefix: null, ...overrides })
const whoami = (overrides: Partial<WhoAmI> = {}): WhoAmI => ({ auth_enabled: true, bootstrap_key_configured: false, managed_keys_active: true, protect_reads: false, authenticated: false, principal: principal(), ...overrides })

describe("access summary", () => {
  it("is unknown before /v1/auth/whoami answers", () => {
    expect(accessSummary(null)).toEqual({ label: "UNKNOWN", tone: "gray", canAdmin: false })
  })
  it("flags open mode, where everyone can administer", () => {
    const summary = accessSummary(whoami({ auth_enabled: false, principal: principal({ scopes: ["read", "write", "admin"] }) }))
    expect(summary.tone).toBe("amber")
    expect(summary.canAdmin).toBe(true)
  })
  it("asks for a key when auth is on and none is entered", () => {
    expect(accessSummary(whoami())).toMatchObject({ label: "NO KEY ENTERED", canAdmin: false })
  })
  it("names the key owner and scopes, granting admin only with the admin scope", () => {
    const member = accessSummary(whoami({ authenticated: true, principal: principal({ kind: "key", scopes: ["read", "write"], email: "a@b.org", key_prefix: "ak_12345678" }) }))
    expect(member).toEqual({ label: "a@b.org · ak_12345678 · READ+WRITE", tone: "teal", canAdmin: false })
    const bootstrap = accessSummary(whoami({ authenticated: true, principal: principal({ kind: "bootstrap", scopes: ["read", "write", "admin"] }) }))
    expect(bootstrap.label.startsWith("BOOTSTRAP KEY")).toBe(true)
    expect(bootstrap.canAdmin).toBe(true)
  })
})
