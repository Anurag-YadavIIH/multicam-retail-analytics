# Contributing

1. Fork → feature branch (`feat/<name>` or `fix/<name>`)
2. `make lint && make test` must pass (CI enforces ruff, black, pytest, docker builds,
   Trivy scan)
3. Conventional commits (`feat: …`, `fix: …`, `docs: …`)
4. PRs need: what/why, screenshots for UI changes, migration note if schema changed
5. Keep coverage ≥85% on backend/analytics/tracking; pure-python domain logic requires
   unit tests, endpoints require integration tests
