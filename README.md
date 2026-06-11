# Team Task Manager

[![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.1-092E20?logo=django&logoColor=white)](https://www.djangoproject.com/)
[![DRF](https://img.shields.io/badge/DRF-3.15-A30000?logo=django&logoColor=white)](https://www.django-rest-framework.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![JWT](https://img.shields.io/badge/Auth-JWT-000000?logo=jsonwebtokens&logoColor=white)](https://django-rest-framework-simplejwt.readthedocs.io/)
![OpenAPI Docs](https://img.shields.io/badge/API-OpenAPI%20%2F%20Swagger-85EA2D?logo=swagger&logoColor=black)
[![Render](https://img.shields.io/badge/Deploy-Render-46E3B7?logo=render&logoColor=black)](https://render.com/)

Team Task Manager (TTM) is a backend-first Django SaaS project for team workspaces, projects, tasks, comments, and audit activity.

The project is intentionally built around service-oriented domain logic, selector-based reads, and centralized permission helpers instead of fat models, views, or serializers.

## Overview

TTM models a workspace-driven collaboration flow:

- users join workspaces through memberships and invitations
- workspaces contain projects
- projects contain tasks
- tasks support assignment, status updates, priorities, due dates, and comments
- important mutations are recorded in an activity log

The HTML interface is intentionally minimal and server-rendered. It exists as a lightweight functional surface for the backend, not as a frontend-heavy product.

## Current UI

The UI is intentionally lightweight, but the project includes a polished server-rendered surface for demo and manual QA flows.

### Dashboard

![Dashboard](docs/screenshots/dashboard.png)

### Workspace Members and Invitations

![Workspace members](docs/screenshots/workspace-members.png)

### Project Detail

![Project detail](docs/screenshots/project-detail.png)

### Task Detail

![Task detail](docs/screenshots/task-detail.png)

### API Docs

![Swagger UI](docs/screenshots/api-docs.png)

## Current Capabilities

- workspace creation and membership-based access control
- invitation creation, acceptance, and revocation
- role management for `owner`, `admin`, and `member`
- explicit workspace ownership transfer
- project archiving and unarchiving
- read-only enforcement for archived projects
- task creation, editing, assignment, and status changes
- comment soft delete with permission boundaries
- activity log for key workspace events
- JWT-authenticated REST API with Swagger/OpenAPI docs
- health and readiness endpoints for deployment
- local Codex automation through management commands and MCP tools

## Stack

- Python 3.13
- Django 5.1
- Django REST Framework
- Simple JWT
- PostgreSQL via `DATABASE_URL`
- SQLite fallback for local development when `DATABASE_URL` is unset
- WhiteNoise for static files
- Render-ready deployment config

## Architecture

TTM follows a strict domain architecture:

- `services` handle state changes and business workflows
- `selectors` handle read/query use cases
- `core.permissions` contains centralized authorization rules
- views, forms, and serializers remain thin
- multi-step mutations use `transaction.atomic()`

### Domain apps

- `accounts`: profile model and authentication pages
- `workspaces`: workspaces, memberships, invitations, ownership workflows
- `projects`: projects inside workspaces, archive lifecycle
- `tasks`: tasks, assignment, status changes, task maintenance workflows
- `comments`: task comments with soft delete
- `activity`: append-only workspace activity log
- `api`: DRF endpoints and JWT auth
- `core`: shared permissions, slugs, exceptions, health checks, agent automation, MCP server

## Project Structure

```text
team_task_manager/
|-- .github/
|-- accounts/
|-- activity/
|-- api/
|-- comments/
|-- core/
|-- docs/
|-- projects/
|-- tasks/
|-- team_task_manager/
|-- templates/
`-- workspaces/
```

Important files:

- `team_task_manager/settings.py`: Django settings, `DATABASE_URL`, DRF, static handling
- `team_task_manager/urls.py`: HTML, API, docs, health, and readiness routes
- `core/permissions.py`: centralized permission checks
- `core/slugs.py`: immutable slug generation helpers
- `core/health.py`: readiness and liveness checks
- `core/agent.py`: local automation workflows for Codex-style agents
- `core/mcp_server.py`: native MCP server for Codex
- `workspaces/services.py`: invitation, membership, and ownership workflows
- `projects/services.py`: project create/archive/unarchive workflows
- `tasks/services.py`: task creation, update, assignment, status, and archived-project guards
- `comments/services.py`: comment create/delete workflows with soft delete behavior
- `activity/services.py`: append-only activity writer
- `api/serializers.py`: thin serializers delegating writes to services
- `api/views.py`: DRF endpoints reusing the same domain logic as HTML flows

## Where Domain Logic Lives

- write logic lives in app services such as `workspaces/services.py`, `projects/services.py`, `tasks/services.py`, and `comments/services.py`
- read logic lives in selectors such as `workspaces/selectors.py`, `projects/selectors.py`, `tasks/selectors.py`, `comments/selectors.py`, and `activity/selectors.py`
- permission rules live in `core/permissions.py`
- HTML views and DRF serializers call those layers instead of implementing business logic inline

## Quick Start

TTM is PostgreSQL-first in local development. SQLite remains available as a secondary fallback for quick demos and agent smoke tests when `DATABASE_URL` is intentionally unset.

Recommended Windows flow:

1. Copy environment settings:

```bash
copy .env.example .env
```

2. Set `DATABASE_URL` to your local PostgreSQL instance.
3. Bootstrap the local environment:

```bash
bootstrap_ttm_local.cmd
```

4. Seed demo data when you want a ready-to-browse workspace:

```bash
seed_ttm_demo.cmd
```

5. Start the local server:

```bash
start_ttm_local.cmd
```

Manual flow:

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy environment settings:

```bash
copy .env.example .env
```

4. Update `.env` values as needed.

5. Run migrations:

```bash
python manage.py migrate
```

6. Create a superuser:

```bash
python manage.py createsuperuser
```

7. Start the local server:

```bash
python manage.py runserver
```

The project reads `.env` automatically. If `DATABASE_URL` is omitted, Django falls back to local SQLite at `db.sqlite3`. That path is supported for quick local use, but PostgreSQL is the main development target.

## Database Configuration

TTM reads the main database connection from `DATABASE_URL`.

Example local PostgreSQL value:

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/team_task_manager
DB_SSL_REQUIRE=False
```

If `DATABASE_URL` is not set, local commands and Codex automation use:

```text
sqlite:///db.sqlite3
```

That fallback is convenient for development, but production should always use PostgreSQL.

## Local Tooling

Windows-friendly helper scripts in the repository root:

- `bootstrap_ttm_local.cmd`: rebuild `.venv`, install dependencies, and run migrations
- `start_ttm_local.cmd`: run the site on `127.0.0.1:8000`
- `test_ttm_local.cmd`: run the Django test suite
- `lint_ttm_local.cmd`: run `ruff`
- `coverage_ttm_local.cmd`: run the full test suite with coverage and enforce the local threshold
- `seed_ttm_demo.cmd`: create or refresh deterministic demo data
- `check_ttm_integrity.cmd`: run domain integrity checks and return non-zero on failures

`bootstrap_ttm_local.cmd` prefers `py -3.13` when it is healthy and falls back to the bundled Codex Python runtime when the Windows launcher is unavailable or broken.

Useful variants:

- `seed_ttm_demo.cmd --reset`: rebuild demo users and workspace from scratch

## Deployment

### Render

The repository includes `render.yaml` and `build.sh` for Render deployment.

Render behavior:

- installs dependencies in `build.sh`
- collects static files during build
- runs migrations in `preDeployCommand`
- starts Gunicorn with a Uvicorn worker
- uses `/healthz/` for health checks
- exposes `/readyz/` for deeper readiness validation
- auto-configures secure proxy and HTTPS-related settings when `RENDER` is present

Blueprint flow:

1. Push the repository with `render.yaml`.
2. Create a new Blueprint in Render.
3. Render provisions the web service and PostgreSQL database.
4. Create an admin user from the Render shell:

```bash
python manage.py createsuperuser
```

Manual Render values:

- Build Command: `./build.sh`
- Pre-Deploy Command: `python manage.py migrate --no-input`
- Start Command: `python -m gunicorn team_task_manager.asgi:application -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT`

### Docker

The repository also includes a production-oriented Docker setup:

- `Dockerfile`
- `docker-compose.yml`
- `docker/entrypoint.sh`

Typical startup flow:

1. `python manage.py migrate --noinput`
2. `python manage.py collectstatic --noinput`
3. `gunicorn` on port `8000`

Example:

```bash
docker compose up --build -d
docker compose logs -f web
docker compose down
```

## HTML Routes

Key server-rendered routes:

- `/`
- `/healthz/`
- `/readyz/`
- `/accounts/signup/`
- `/accounts/login/`
- `/workspaces/`
- `/workspaces/create/`
- `/workspaces/<slug>/`
- `/workspaces/<slug>/members/`
- `/workspaces/<slug>/members/<membership_id>/role/`
- `/workspaces/<slug>/members/<membership_id>/remove/`
- `/workspaces/<slug>/invitations/<invitation_id>/revoke/`
- `/workspaces/<slug>/transfer-ownership/`
- `/workspaces/<slug>/activity/`
- `/invitations/<token>/accept/`
- `/workspaces/<workspace_slug>/projects/`
- `/workspaces/<workspace_slug>/projects/<project_slug>/`
- `/workspaces/<workspace_slug>/projects/<project_slug>/archive/`
- `/workspaces/<workspace_slug>/projects/<project_slug>/unarchive/`
- `/workspaces/<workspace_slug>/projects/<project_slug>/tasks/`
- `/workspaces/<workspace_slug>/projects/<project_slug>/tasks/<task_slug>/`
- `/workspaces/<workspace_slug>/projects/<project_slug>/tasks/<task_slug>/edit/`

## API

### Authentication

- `POST /api/auth/token/`
- `POST /api/auth/token/refresh/`

### Workspaces and membership

- `GET, POST /api/workspaces/`
- `GET /api/workspaces/<slug>/`
- `GET /api/workspaces/<slug>/activity/`
- `GET, POST /api/workspaces/<slug>/invitations/`
- `DELETE /api/workspaces/<slug>/invitations/<invitation_id>/`
- `GET, PATCH, DELETE /api/workspaces/<slug>/memberships/<membership_id>/`
- `POST /api/workspaces/<slug>/transfer-ownership/`
- `POST /api/invitations/<token>/accept/`

### Projects

- `GET, POST /api/projects/`
- `GET /api/workspaces/<workspace_slug>/projects/<project_slug>/`
- `POST /api/workspaces/<workspace_slug>/projects/<project_slug>/archive/`
- `POST /api/workspaces/<workspace_slug>/projects/<project_slug>/unarchive/`

### Tasks and comments

- `GET, POST /api/tasks/`
- `POST /api/tasks/bulk-update/`
- `GET, PATCH /api/workspaces/<workspace_slug>/projects/<project_slug>/tasks/<task_slug>/`
- `GET, POST /api/comments/`
- `DELETE /api/comments/<id>/`

### Activity

- `GET /api/activity/`
- `GET /api/workspaces/<slug>/activity/`

### Useful query params

- `/api/projects/?workspace=<workspace-slug>`
- `/api/projects/?is_archived=true`
- `/api/projects/?created_by=<user-id>`
- `/api/projects/?q=analytics`
- `/api/projects/?ordering=created_at`
- `/api/tasks/?project=<project-slug>`
- `/api/tasks/?workspace=<workspace-slug>`
- `/api/tasks/?status=todo`
- `/api/tasks/?priority=high`
- `/api/tasks/?assignee=<user-id>`
- `/api/tasks/?created_by=<user-id>`
- `/api/tasks/?due_before=2026-06-30`
- `/api/tasks/?due_after=2026-06-01`
- `/api/tasks/?is_overdue=true`
- `/api/tasks/?q=release`
- `/api/tasks/?ordering=-created_at`
- `/api/comments/?task=<task-slug>`
- `/api/comments/?author=<user-id>`
- `/api/comments/?is_deleted=false`
- `/api/comments/?q=note`
- `/api/activity/?workspace=<workspace-slug>`
- `/api/activity/?actor=<user-id>`
- `/api/activity/?action=task_status_changed`
- `/api/activity/?target_type=task`
- `/api/activity/?ordering=-created_at`

### API docs

- Swagger UI: `/api/docs/`
- OpenAPI schema: `/api/schema/`

Example:

```bash
curl -X POST http://127.0.0.1:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"owner\",\"password\":\"secret123\"}"
```

Bulk task maintenance example:

```bash
curl -X POST http://127.0.0.1:8000/api/tasks/bulk-update/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d "{
    \"workspace_slug\": \"engineering\",
    \"project_slug\": \"backend\",
    \"task_slugs\": [\"ship-api\", \"write-docs\"],
    \"status\": \"done\",
    \"assignee_id\": 3
  }"
```

## Agent Automation

TTM exposes a local command-driven automation layer for Codex-style agents.

These commands call Django services directly, so they reuse the same permissions, slug rules, and activity logging as the HTML and API layers.

Useful commands:

```bash
python manage.py agent_list_workspaces --actor owner
python manage.py agent_list_projects --actor owner --workspace engineering
python manage.py agent_list_members --actor owner --workspace engineering
python manage.py agent_list_tasks --actor owner --workspace engineering --project backend
python manage.py agent_create_project --actor owner --workspace engineering --name "Ops Console"
python manage.py agent_create_task --actor owner --workspace engineering --project backend --title "Add audit export"
python manage.py agent_update_task --actor owner --workspace engineering --project backend --task ship-api --status done
```

Higher-level request capture:

```bash
python manage.py agent_capture_request --actor owner --request "action: create_task
workspace: Engineering
project: Backend
title: Add audit export
description: Build a command for exporting workspace activity
priority: high
assignee: alice"
```

Preview before writing:

```bash
python manage.py agent_capture_request --actor owner --preview --request "action: create_task
workspace: Engineering
project: Backend
title: Preview task only"
```

Batch requests are supported with `---` separators, and file-based workflows are available through `agent_apply_file`.

Markdown checklists also work for bulk task creation and maintenance, including `Task Action: update_task`.

Structured requests can also use Russian keys and values.

## Codex MCP Mode

The repo also exposes a native MCP server at [`core/mcp_server.py`](core/mcp_server.py).

That server wraps the same Django domain services used by HTML, API, and management commands, so Codex can operate on TTM through local tools instead of browser automation.

Available MCP tools:

- `ttm_get_context`
- `ttm_list_workspaces`
- `ttm_list_projects`
- `ttm_list_members`
- `ttm_list_tasks`
- `ttm_create_project`
- `ttm_create_task`
- `ttm_update_task`
- `ttm_close_task`
- `ttm_apply_request`
- `ttm_apply_file`

The MCP server supports `TTM_AGENT_DEFAULT_ACTOR`, which makes repeated Codex-driven operations simpler in local workflows.

## Testing and Quality Checks

Full test suite:

```bash
python manage.py test
```

Useful checks:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python -m ruff check .
```

Coverage:

```bash
coverage run --source=accounts,activity,api,comments,core,projects,tasks,workspaces manage.py test
coverage report --show-missing --fail-under=85
```

Operational endpoints:

- `GET /healthz/`: liveness probe for the Django process
- `GET /readyz/`: readiness probe that verifies database access and unapplied migrations

Operational commands:

- `python manage.py seed_demo_data`
- `python manage.py seed_demo_data --reset`
- `python manage.py check_domain_integrity`

## CI

GitHub Actions runs on pushes to `master` and on pull requests.

The workflow:

- installs dependencies on Python 3.13
- runs a dedicated `lint` job
- runs a dedicated `django-check` job with migration drift checks
- runs PostgreSQL-backed tests
- enforces `85%` total coverage and publishes a coverage artifact from a separate coverage job
