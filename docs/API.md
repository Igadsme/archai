# API

`GET /health` is unauthenticated and reports service readiness. `POST /v1/architectures/validate` accepts a strict Architecture JSON document and returns its canonical hash plus analytical metrics. `POST /v1/architectures`, `GET /v1/architectures`, and `GET /v1/architectures/{architecture_id}` provide the local registry surface. If `ARCHAI_API_KEY` is configured, write operations require the `x-api-key` header. Generator and expensive job endpoints remain disabled until authenticated deployment configuration and a real checkpoint are present.
