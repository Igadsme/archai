import { describe, expect, it } from "vitest"
import { curlExample, weightsBadge } from "../app/screens/Deployments"

describe("deployment weights badge", () => {
  it("never calls seeded weights trained", () => {
    expect(weightsBadge({ trained: false, model: null })).toEqual({ text: "UNTRAINED WEIGHTS", tone: "amber" })
    expect(weightsBadge({ trained: true, model: null }).text).toBe("UNTRAINED WEIGHTS")
  })
  it("names the verified checkpoint", () => {
    expect(weightsBadge({ trained: true, model: { model_id: "cand", version: "2", sha256: "ab", kind: "candidate" } })).toEqual({ text: "CHECKPOINT cand@2", tone: "teal" })
  })
})

describe("curl example", () => {
  it("reads the key from the environment instead of embedding it", () => {
    const command = curlExample({ predict_path: "/v1/deployments/abc/predict" })
    expect(command).toContain("/v1/deployments/abc/predict")
    expect(command).toContain("$ARCHAI_API_KEY")
  })
})
