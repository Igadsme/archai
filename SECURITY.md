# Security

Architecture specifications are untrusted data. The compiler uses an allowlisted operator registry and does not dynamically import or execute user code. Checkpoints should be loaded with safe formats and verified hashes. Expensive jobs require an authenticated deployment-level policy, quotas, cancellation, and audit logging before enabling them. State-changing API requests are audit-logged (see `docs/API.md`); per-client rate limits are shared through Redis when configured, with an in-process fallback.
