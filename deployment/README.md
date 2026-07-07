# Deployment targets

- `docker-compose.yml` (repo root) — local lite/full stacks. Start here.
- Kubernetes/Helm: planned (see TASKS.md). The images built by
  `docker/backend.Dockerfile`, `docker/vision.Dockerfile`, `docker/frontend.Dockerfile`
  are 12-factor (config via env) and k8s-ready as-is: backend needs
  `DATABASE_URL/REDIS_URL/SECRET_KEY`; the vision worker only needs `BACKEND_URL` +
  `SECRET_KEY`, so it can run as a DaemonSet on edge nodes.
