# WorkWings

WorkWings is a controlled multi-agent workflow platform for software delivery. It combines a React workbench with a FastAPI workflow backend so that agent execution is structured, reviewable, auditable, and persisted to project storage.

The platform is designed for delivery workflows that need both model-assisted productivity and deterministic control boundaries:

```text
create project
  -> upload text or image materials
  -> multimodal analysis
  -> project analysis
  -> human confirmation
  -> requirement baseline
  -> prototype generation
  -> architecture analysis
  -> development
  -> workspace apply
  -> testing
  -> security review
  -> project delivery
```

## Core Principles

- `WorkflowEngine` is the only owner of workflow state transitions.
- Agents produce validated structured artifacts and do not directly mutate workflow state.
- Cross-agent collaboration uses persisted `ArtifactRef` values and versioned schemas.
- Human approval is a first-class checkpoint with events, audit records, and recovery support.
- Platform storage is the source of truth for artifacts, workflow runs, checkpoints, and audit history.
- Long-running work can be distributed through the queue layer, while the workflow engine remains responsible for deciding the next node.
- Project file writes are constrained by workspace boundaries and must not escape the current project directory.
- Production configuration is injected through environment variables; secrets are never committed to the repository.

## Agent Workflow

The default `project_discovery_v1` workflow contains nine registered delivery agents in this order:

| Order | Agent | Responsibility | Typical output |
| ---: | --- | --- | --- |
| 01 | `multimodal_analysis_agent` | Parse text and image materials | Material analysis artifact |
| 02 | `project_analysis_agent` | Inspect project context and delivery goals | Project analysis artifact |
| 03 | `requirement_baseline_agent` | Turn evidence into a reviewable requirement baseline | Requirement baseline document |
| 04 | `prototype_generation_agent` | Define prototype pages, interactions, and design evidence | Prototype specification and preview artifacts |
| 05 | `architecture_agent` | Produce backend, frontend, data, API, and deployment architecture | Architecture and OpenAPI artifacts |
| 06 | `development_agent` | Prepare implementation changes and project files | Development plan and implementation artifacts |
| 07 | `testing_agent` | Define and record verification evidence | Test plan and test result artifacts |
| 08 | `security_agent` | Review boundaries, permissions, and deployment risks | Security review artifact |
| 09 | `project_delivery_agent` | Assemble the release handoff | Delivery runbook and release artifact |

The approval checkpoint follows project analysis. Subsequent agents run only after the human confirmation is accepted by the workflow engine.

## Repository Layout

```text
backend/                       FastAPI application and domain modules
backend/app/api/               HTTP, SSE, auth hooks, and response shaping
backend/app/application/       Use cases and transaction boundaries
backend/app/domain/            Entities, enums, ports, and state rules
backend/app/orchestration/     Workflow graph, engine, checkpoints, and events
backend/app/agent_runtime/     Agent registry, execution, validation, and model routing
backend/app/agents/            The nine delivery agent modules
backend/app/infrastructure/    Database, storage, queue, search, and model adapters
backend/migrations/            Alembic environment and migration revisions
frontend/                      React + TypeScript workbench
workflow_templates/            Versioned workflow definitions
deploy/production/              Production initialization and operations assets
deploy/nginx/                  Reverse-proxy configuration
docs/                           Architecture and development documentation
docs-dev/                       Source requirement and planning documents
scripts/                        Backup, restore, rollback, and operational helpers
```

## Technology Stack

### Workbench

- React 19 and React DOM
- TypeScript with strict project configuration
- Vite for local development and production asset builds
- Vitest and Testing Library for frontend tests
- Playwright for browser-level verification
- React Flow for visual workflow composition where enabled

### Workflow backend

- Python 3.12+
- FastAPI and Uvicorn
- Deterministic `WorkflowEngine` orchestration
- Structured agent runtime with output validation and model routing
- Alembic migrations
- Server-Sent Events for workflow and execution streams

### Data and platform services

- MySQL for platform metadata, workflow state, artifacts, audit records, and checkpoints
- Redis for cache, locks, and short-lived event fan-out
- Elasticsearch for per-agent knowledge indexes
- MinIO-compatible object storage for uploaded materials and generated artifacts
- Docker Compose for production service orchestration
- Nginx as the production reverse proxy

## Local Development

### Requirements

- Python 3.12 or newer
- Node.js compatible with the repository toolchain
- pnpm
- MySQL, Redis, Elasticsearch, and MinIO when exercising integrations or full workflow execution

### Configure the environment

Copy the example environment file and fill in local-only values. Never commit `.env` or any credential file:

```powershell
Copy-Item .env.example .env
```

The backend must use an explicit database URL. Do not rely on SQLite or an in-memory database for production-like verification.

### Install and verify the backend

```powershell
python -m pip install -e ".[dev]"
ruff format --check .
ruff check .
pyright
pytest
```

### Apply migrations

```powershell
alembic -c backend/alembic.ini upgrade head
```

Migrations are additive and versioned under `backend/migrations/versions/`. Review the target database and migration plan before applying changes to a shared environment.

### Start the API

```powershell
python -m uvicorn app.main:app --app-dir backend --reload --host 0.0.0.0 --port 8000
```

The API health endpoint is `GET /api/v1/health`.

### Start the workbench

```powershell
pnpm install --frozen-lockfile=false
pnpm dev
```

The frontend development proxy is configured by the Vite application. Set the API base URL through the environment rather than hard-coding a production endpoint into source code.

### Frontend checks

```powershell
pnpm lint
pnpm test
pnpm build
```

## Production Deployment

Production deployment is designed for Docker Compose and keeps internal services off the public network. The public entry point is the Nginx reverse proxy; MySQL, Redis, Elasticsearch, MinIO, the migration job, and the worker remain internal services.

```powershell
Copy-Item .env.production.example .env.production
docker compose --env-file .env.production -f docker-compose.production.yml config
docker compose --env-file .env.production -f docker-compose.production.yml build
docker compose --env-file .env.production -f docker-compose.production.yml up -d
```

The production Compose file coordinates service readiness, runs Alembic before the API starts, provisions the object-storage bucket, and exposes only the reverse proxy ports. Use the operations documentation under `deploy/production/` for backups, restore, health checks, and rollback procedures.

Production requirements:

- Supply every required variable in `.env.production` through the deployment environment or secret manager.
- Keep model API keys, database passwords, object-storage credentials, tokens, cookies, and certificates outside Git.
- Configure HTTPS certificates and the frontend/API origin policy before exposing the reverse proxy.
- Review image tags and the rollback version before every release.
- Verify health, migrations, SSE, approvals, artifact persistence, and workspace write boundaries after deployment.

## API and Event Model

The backend exposes REST endpoints for projects, workflow runs, approvals, artifacts, and health information. SSE endpoints stream persisted execution facts such as agent messages, command execution, approval events, state transitions, and artifact updates.

Agents communicate through validated artifact contracts. A downstream node receives an `ArtifactRef`, loads the persisted artifact, validates its schema, and produces its own output. Natural-language output is not used as an implicit workflow control channel.

## Security Boundaries

- High-risk tools require permission checks, approval, sandboxing, and audit records.
- Agents cannot approve their own outputs or directly advance workflow state.
- Production containers use non-root images or users, read-only filesystems where supported, dropped capabilities, and isolated networks.
- Database, Redis, Elasticsearch, and object storage are not published to the public network.
- Health responses and logs must redact secrets and connection credentials.
- Deployment agents prepare release instructions; they do not execute production deployment commands.

## Documentation

- Development admission rules: `docs/development/admission-gate.md`
- Architecture boundaries: `docs/architecture/`
- Infrastructure responsibilities: `docs/development/infrastructure.md`
- Versioned workflow: `workflow_templates/project_discovery_v1.yaml`
- Production deployment guide: `deploy/production/README.md`
- Environment variable reference: `.env.example` and `.env.production.example`

## Project Status

WorkWings currently provides the controlled project-discovery workflow foundation, agent contracts, approval checkpoint, event and audit persistence, artifact storage boundaries, and production deployment assets. Individual model-provider integrations, external queue scheduling, and end-to-end production integrations still depend on the environment variables and services configured for the target deployment.
