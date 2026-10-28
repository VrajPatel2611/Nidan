# Architecture Decision Records

One decision per file. **Never edit an accepted ADR** — supersede it with a new one.

| ADR | Decision | Status |
|---|---|---|
| [0001](0001-postgresql-with-pgvector-hosted-on-supabase.md) | PostgreSQL + pgvector on Supabase | Accepted |
| [0002](0002-supabase-auth-rather-than-custom-authentication.md) | Supabase Auth, not custom | Accepted |
| [0003](0003-event-sourced-session-state.md) | Event-sourced session state | Accepted |
| [0004](0004-rule-based-bias-detection-not-machine-learning.md) | Rule-based detection, not ML | Accepted |
| [0005](0005-the-llm-is-excluded-from-the-marking-path.md) | LLM excluded from the marking path | Accepted |
| [0006](0006-nextjs-for-the-consumer-app-jinja-+-htmx-for-admin.md) | Next.js consumer, Jinja+HTMX admin | Accepted |
| [0007](0007-retain-flask-do-not-migrate-to-fastapi.md) | Retain Flask, not FastAPI | Accepted |
| [0008](0008-deploy-to-render-(or-railway)-not-vercel.md) | Render/Railway, not Vercel | Accepted |
| [0009](0009-modular-monolith-not-microservices.md) | Modular monolith | Accepted |
| [0010](0010-cases-are-immutable-and-versioned.md) | Immutable versioned cases | Accepted |
| [0011](0011-per-job-llm-routing-rather-than-one-model.md) | Per-job LLM routing | Accepted |
| [0012](0012-natural-language-inference-for-grounding-not-an-llm.md) | NLI for grounding, not LLM | Accepted |
| [0013](0013-prebuilt-embeddings-first-fine-tune-later.md) | Prebuilt embeddings, fine-tune later | Accepted |
| [0014](0014-no-case-retirement-policy-use-variants-instead.md) | No retirement; variants instead | Accepted |
| [0015](0015-direct-to-consumer-with-the-institutional-path-preserve.md) | B2C, institutional path preserved | Accepted |
| [0016](0016-tenant-scoping-by-per-transaction-role-assumption.md) | Tenant scoping by per-transaction role assumption | Accepted |
| [0017](0017-data-residency-eu-frankfurt.md) | Data residency in the EU (Frankfurt) | Accepted |

## Template

```markdown
# ADR-NNNN · Title
| Status | Proposed / Accepted / Superseded by ADR-XXXX |
## Context      — the forces at play, factually
## Decision     — what we chose, stated plainly
## Alternatives — what we rejected and why
## Consequences — good and bad, honestly
```
