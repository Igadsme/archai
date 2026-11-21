# API

`GET /health` is unauthenticated and reports service readiness. `POST /v1/architectures/validate` accepts a strict Architecture JSON document and returns its canonical hash plus analytical metrics. Generator and expensive job endpoints remain disabled until authenticated deployment configuration and a real checkpoint are present.
