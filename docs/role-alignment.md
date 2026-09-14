# Role alignment: Full Stack Developer

This project is intentionally shaped as a portfolio proof point for a Node.js / Python / SQL / Docker role in healthcare operations.

| Role signal | Evidence in this repository |
| --- | --- |
| Node.js, NestJS, Express | `apps/api/src/nest-main.ts`, `nest.module.ts`, and Express-compatible REST routes |
| React and Next.js | `apps/web/app/page.tsx` and responsive dashboard styles |
| PostgreSQL and SQL | `apps/api/migrations/001_initial.sql`, relational schema, foreign keys, and search indexes |
| Python automation | `worker/reminders.py`, a dry-run reminder report with deterministic synthetic inputs |
| REST/API integration | JWT auth, OpenAPI docs, mock clearinghouse eligibility adapter, Supertest coverage |
| Docker | Separate API/web Dockerfiles and `docker-compose.yml` |
| CI/CD | GitHub Actions test, lint, build, and optional SonarQube scan workflows |
| Code quality | PR template, lint configuration, typed code, tests, ADR, and explicit risk notes |
| Deployment awareness | Render blueprint plus Azure deployment notes below |

## Honest demo boundary

This is a portfolio application, not a clinical or billing system. It uses fake records, a demo JWT flow, an in-memory fallback store for preview mode, and a deterministic external-service mock. A production implementation would replace those boundaries with OIDC, PostgreSQL repositories, secret management, audit retention controls, threat modeling, and a reviewed healthcare compliance program.

## Interview walkthrough

1. Start with the API contract and synthetic-data boundary.
2. Show the appointment overlap check and its Supertest regression test.
3. Explain the PostgreSQL indexes and how `sortBy`, `order`, `q`, `page`, and `limit` map to query behavior.
4. Run the Python reminder worker and explain why it is dry-run only.
5. Review Docker Compose, CI, the PR template, and the optional SonarQube job.
6. Discuss the production gaps openly instead of presenting demo shortcuts as finished healthcare infrastructure.
