export type Metrics = { parameters: number; flops: number; activation_memory_bytes: number }
export type ArchitectureItem = { architecture_id: string; search_space: string; metrics: Metrics }
export type SearchItem = { search_id: string; algorithm: string; dataset_id: string; status?: string; seed: number; budget_evaluations?: number }
export type ExperimentItem = { experiment_id: string; architecture_id: string; evidence_type: string; status: string; metrics: Record<string, number>; provenance?: { dataset_id?: string; seed?: number; code_revision?: string } }
export type DatasetItem = { dataset_id: string; version: string; checksum: string; uri?: string; license?: string | null }
export type JobItem = { job_id: string; kind: string; status: string; error: string | null; payload?: Record<string, unknown>; created_at?: string; updated_at?: string }
export type ModelItem = { model_id: string; kind: string; version: string; sha256: string; artifact_exists?: boolean; integrity_verified?: boolean }
export type ArchitectureNode = { id: string; op: string; channels: number }
export type ArchitectureDocument = { architecture: { nodes: ArchitectureNode[]; edges: { source: string; target: string }[] }; hash: string; metrics?: Metrics }
export type Readiness = { status: string; durable_worker_configured: boolean; database_configured: boolean; database_ready: boolean; rate_limit_backend?: string; rate_limit_redis_error?: string | null }
export type AuditEvent = { timestamp: string; method: string; path: string; status: number; outcome: "allowed" | "rejected"; client: string | null; credential_fingerprint: string | null; duration_ms: number; request_id?: string | null }
export type AuditLog = { available: boolean; items: AuditEvent[]; detail?: string }
export type Worker = { worker_id: string; hostname: string; status: string; last_seen: string; active_job_id: string | null }
export type ArchitectureEdge = { source: string; target: string }
export type FullArchitecture = {
  nodes: (ArchitectureNode & { kernel_size?: number; activation?: string; normalization?: string })[]; edges: ArchitectureEdge[]
  input_spec: { channels: number; height: number; width: number }; output_classes: number; search_space?: string
  architecture_id?: string | null; schema_version?: string; generator_version?: string; seed?: number | null; lineage?: string[]; metadata?: Record<string, string>
}
/** Response of POST /v1/architectures/validate, POST /v1/architectures and GET /v1/architectures/{id}. */
export type ArchitectureDetail = { architecture: FullArchitecture; hash: string; analytical_metrics: AnalyticalMetrics }
export type AnalyticalMetrics = { parameters: number; flops: number; activation_memory_bytes: number }
export type CompareItem = { architecture_id: string; architecture: FullArchitecture; analytical_metrics: AnalyticalMetrics }
export type SearchAlgorithm = { name: string; label: string; description: string; parameters: string[]; available: boolean; unavailable_reason: string | null }
export type HistoryStep = { step: number; index: number; architecture_string?: string; validation_accuracy: number; params_m?: number; flops_m?: number }
export type JobDetail = JobItem & { result?: Record<string, unknown> | null; updated_at?: string }
export type SeedSummary = { mean: number; ci_low: number; ci_high: number; std: number; n_seeds: number }
export type ResearchReport = { algorithms: Record<string, { runs: number; best_validation_accuracy: SeedSummary; final_test_accuracy?: SeedSummary; hypervolume_validation_params?: SeedSummary; search_cost?: SeedSummary }>; matched_budget?: number; experiment?: string; evidence_type?: string; ablations?: string[] }
export type ParetoPoint = { index: number; architecture_string?: string; validation_accuracy: number; params_m: number; flops_m?: number }
export type ParetoData = { objectives: Record<string, string>; evidence_type: string; hypervolume_reference: number[]; full_space_front_trial_seed_for_seed0: ParetoPoint[]; policies: Record<string, Record<string, { front: ParetoPoint[]; hypervolume: number | null }>> }
export type ResearchResult = { name: string; report?: ResearchReport; pareto?: ParetoData; readme?: string; tables?: string; predictor?: Record<string, unknown>; generator?: Record<string, unknown>; checkpoint_verification?: Record<string, unknown>; regret?: Record<string, SeedSummary>; experiment?: ExperimentConfig }
export type ModelInspection = ModelItem & { path?: string; top_level_keys: string[]; tensor_count: number; parameter_count: number; tensors: { name: string; shape: number[]; dtype: string }[]; checkpoint_metadata: Record<string, unknown> | null }
export type ExperimentConfig = { name: string; description?: string; budget: number; seeds: number[]; algorithms: string[]; ablations?: { name: string; algorithm: string; params: Record<string, unknown> }[] }

export type ArchitectureConstraints = { max_parameters?: number | null; max_flops?: number | null; max_latency_s?: number | null; allowed_ops?: string[] | null }
export type ResearchProject = { project_id: string; name: string; description: string; task: string; dataset_id?: string | null; dataset_version?: string | null; constraints: ArchitectureConstraints; status: "active" | "archived"; created_at: string; updated_at: string }
export type Principal = { kind: "anonymous" | "bootstrap" | "key"; scopes: string[]; user_id: string | null; email: string | null; credential_id: string | null; key_prefix: string | null }
export type WhoAmI = { auth_enabled: boolean; bootstrap_key_configured: boolean; managed_keys_active: boolean; protect_reads: boolean; authenticated: boolean; principal: Principal }
export type UserItem = { user_id: string; email: string; display_name: string; role: "admin" | "member"; created_at: string; disabled_at: string | null; active: boolean; active_keys?: number }
export type ApiKeyItem = { credential_id: string; user_id: string; name: string; key_prefix: string; scopes: string[]; created_at: string; last_used_at: string | null; expires_at: string | null; revoked_at: string | null; rotated_from: string | null; state: "active" | "expired" | "revoked" }
export type IssuedApiKey = ApiKeyItem & { secret: string; secret_notice: string }
export type GpuDevice = { index: number; name: string; memory_total_bytes: number; memory_used_bytes: number; utilization_percent: number | null; memory_utilization_percent: number | null; temperature_c: number | null; power_watts: number | null }
export type GpuTelemetry = { available: boolean; source: "nvml" | "torch.cuda" | null; devices: GpuDevice[]; reason: string | null }
export type HostTelemetry = { hostname: string; platform: string; python: string; cpu_count: number | null; load_average: number[] | null; memory: { total_bytes: number; available_bytes: number; used_bytes: number } | null; cgroup_memory_limit_bytes: number | null; process_peak_rss_bytes: number }
export type TelemetrySnapshot = { measured_at: string; host: HostTelemetry; gpu: GpuTelemetry }
export type TelemetryResponse = { api: TelemetrySnapshot; workers: { worker_id: string; hostname: string; last_seen: string; telemetry: TelemetrySnapshot | null }[] }
export type LatencyMeasurement = { measurement_id: string; architecture_id: string; evidence_type: "measured_latency"; device: string; hardware: string; platform: string; torch_version: string; threads: number; batch_size: number; iterations: number; truncated_by_time_limit: boolean; mean_ms: number; p50_ms: number; p90_ms: number; p99_ms: number; min_ms: number; max_ms: number; throughput_samples_per_s: number; measured_at: string }

export type DeploymentItem = {
  deployment_id: string; name: string; architecture_id: string; input_shape: [number, number, number]; output_classes: number
  model: { model_id: string; version: string; sha256: string; kind: string } | null
  status: "active" | "stopped"; created_at: string; updated_at: string; created_by: string | null
  stats: { request_count: number; error_count: number; last_request_at: string | null; last_latency_ms: number | null }
  weights: string; trained: boolean; loaded: boolean; predict_path: string
}
export type PredictionResult = {
  deployment_id: string; weights: string; trained: boolean; input_source: string; batch_size: number; served_at: string
  output_shape: number[]; logits: number[][]; predicted_class: number[]; confidence: number[]; latency_ms: number
}
