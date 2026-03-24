# Team Task Manager

[![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.1-092E20?logo=django&logoColor=white)](https://www.djangoproject.com/)
[![DRF](https://img.shields.io/badge/DRF-3.15-A30000?logo=django&logoColor=white)](https://www.django-rest-framework.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![JWT](https://img.shields.io/badge/Auth-JWT-000000?logo=jsonwebtokens&logoColor=white)](https://django-rest-framework-simplejwt.readthedocs.io/)
![OpenAPI Docs](https://img.shields.io/badge/API-OpenAPI%20%2F%20Swagger-85EA2D?logo=swagger&logoColor=black)
[![Render](https://img.shields.io/badge/Deploy-Render-46E3B7?logo=render&logoColor=black)](https://render.com/)

Team Task Manager (TTM) is a backend-first Django SaaS project for team workspaces, projects, tasks, comments, and audit activity.

The project is intentionally built around service-oriented domain logic, selector-based reads, and centralized permission helpers instead of fat views or serializers.

## Stack

- Python 3.13
- Django 5.1
- Django REST Framework
- Simple JWT
- PostgreSQL via `DATABASE_URL`
- Render-friendly static handling with WhiteNoise

## Screenshots

### Workspaces

![Workspace list](docs/screenshots/workspaces.png)

### Workspace Overview

![Workspace detail](docs/screenshots/workspace-detail.png)

### Members

![Workspace members](docs/screenshots/workspace-members.png)

### Tasks

![Task list](docs/screenshots/task-list.png)

### Task Detail

![Task detail](docs/screenshots/task-detail.png)

### API Docs

![Swagger UI](docs/screenshots/api-docs.png)

## Architecture

TTM follows a strict domain architecture:

- `services` handle all state changes and business workflows.
- `selectors` handle read/query use cases.
- `core.permissions` contains centralized authorization helpers.
- views, forms, and serializers stay thin and delegate to services/selectors.
- multi-model workflows use `transaction.atomic()`.

### Domain apps

- `accounts`: profile model and authentication pages
- `workspaces`: workspaces, memberships, invitations
- `projects`: projects inside workspaces
- `tasks`: tasks, assignment, status changes
- `comments`: task comments with soft delete
- `activity`: append-only workspace activity log
- `api`: DRF endpoints and JWT authentication
- `core`: shared permissions, slug utilities, exceptions

## Project Structure

```text
team_task_manager/
|-- accounts/
|-- activity/
|-- api/
|-- comments/
|-- core/
|-- projects/
|-- tasks/
|-- team_task_manager/
|-- templates/
`-- workspaces/
```

Important files:

- `team_task_manager/settings.py`: project configuration, `DATABASE_URL`, DRF, static/media
- `core/permissions.py`: shared permission checks
- `core/slugs.py`: immutable slug generation helpers
- `workspaces/services.py`: workspace ownership and invitation workflows
- `projects/services.py`: project creation workflow
- `tasks/services.py`: task creation, assignment, status change workflows
- `comments/services.py`: comment create and soft delete workflows
- `activity/services.py`: append-only activity writer
- `api/serializers.py`: thin serializers delegating writes to services
- `api/views.py`: DRF endpoints and workspace activity API

## Where Domain Logic Lives

- Write logic lives in app services such as `workspaces/services.py`, `projects/services.py`, `tasks/services.py`, and `comments/services.py`.
- Read logic lives in app selectors such as `workspaces/selectors.py`, `projects/selectors.py`, `tasks/selectors.py`, `comments/selectors.py`, and `activity/selectors.py`.
- Permission rules live in `core/permissions.py`.
- HTML views and DRF serializers call those layers instead of implementing business rules directly.

## Architecture Decisions

- The project uses the default Django `User` model to keep authentication standard and avoid unnecessary custom auth complexity.
- Business workflows live in app-level services so HTML views and DRF endpoints reuse the same write logic.
- Read access is implemented through selectors scoped by membership to keep multi-tenant filtering explicit and testable.
- Authorization rules are centralized in `core.permissions` so access decisions are not reimplemented across views and serializers.
- Slugs are immutable after creation and enforced by scoped unique constraints at the database layer.
- `ActivityLog` is append-only and written only from services to keep audit history consistent without introducing an event bus.
- Comments use soft delete semantics in the UI and API while preserving domain-level permission checks around deletion.

## Quick Start

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy environment settings:

```bash
copy .env.example .env
```

4. Update `DATABASE_URL` and `DJANGO_SECRET_KEY` in `.env`.
   `.env` is loaded automatically by Django settings, so local commands use the configured database without manual environment export.
5. Run migrations:

```bash
python manage.py migrate
```

6. Create a superuser:

```bash
python manage.py createsuperuser
```

7. Start the server:

```bash
python manage.py runserver
```

## PostgreSQL Setup

TTM reads the database connection from `DATABASE_URL`.

Example local PostgreSQL value:

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/team_task_manager
DB_SSL_REQUIRE=False
```

For Render, configure `DATABASE_URL`, `DJANGO_SECRET_KEY`, `DEBUG=False`, and `ALLOWED_HOSTS`.
For external Render Postgres connections, set `DB_SSL_REQUIRE=True` if your URL does not already include SSL parameters.

## Render Deployment

The repository includes [render.yaml](C:/Users/kiril/OneDrive/Рабочий%20стол/TTM/render.yaml) and [build.sh](C:/Users/kiril/OneDrive/Рабочий%20стол/TTM/build.sh) for Render deployment.

Deployment behavior on Render:

- dependencies are installed in `build.sh`
- static files are collected during build
- database migrations run in `preDeployCommand`
- the app starts with Gunicorn and a Uvicorn worker
- `DEBUG` defaults to `False` when the `RENDER` environment variable is present
- `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` automatically include `RENDER_EXTERNAL_HOSTNAME`
- secure proxy, HTTPS redirect, secure cookies, and HSTS are enabled on Render

Blueprint flow:

1. Push the repository with `render.yaml`.
2. In Render, create a new Blueprint from the repository.
3. Render will provision:
   - web service `team-task-manager`
   - PostgreSQL database `team-task-manager-db`
4. After the first deploy, create an admin user from the Render Shell:

```bash
python manage.py createsuperuser
```

Manual Render service values:

- Build Command: `./build.sh`
- Pre-Deploy Command: `python manage.py migrate --no-input`
- Start Command: `python -m gunicorn team_task_manager.asgi:application -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT`

## HTML Pages

- `/`
- `/accounts/signup/`
- `/accounts/login/`
- `/workspaces/`
- `/workspaces/create/`
- `/workspaces/<slug>/`
- `/workspaces/<slug>/members/`
- `/workspaces/<slug>/activity/`
- `/workspaces/<slug>/projects/`
- `/workspaces/<workspace_slug>/projects/<project_slug>/`
- `/workspaces/<workspace_slug>/projects/<project_slug>/tasks/`
- `/workspaces/<workspace_slug>/projects/<project_slug>/tasks/<task_slug>/`
- `/workspaces/<workspace_slug>/projects/<project_slug>/tasks/<task_slug>/edit/`

## API Endpoints

Authentication:

- `POST /api/auth/token/`
- `POST /api/auth/token/refresh/`

Resources:

- `GET, POST /api/workspaces/`
- `GET /api/workspaces/<slug>/`
- `GET, POST /api/projects/`
- `GET /api/workspaces/<workspace_slug>/projects/<project_slug>/`
- `GET, POST /api/tasks/`
- `GET, PATCH /api/workspaces/<workspace_slug>/projects/<project_slug>/tasks/<task_slug>/`
- `GET, POST /api/comments/`
- `DELETE /api/comments/<id>/`
- `GET /api/activity/`
- `GET /api/workspaces/<slug>/activity/`

Useful query params:

- `/api/projects/?workspace=<workspace-slug>`
- `/api/tasks/?project=<project-slug>`
- `/api/tasks/?status=todo`
- `/api/tasks/?assignee=<user-id>`
- `/api/tasks/?ordering=-created_at`
- `/api/projects/?ordering=created_at`
- `/api/activity/?ordering=-created_at`
- `/api/comments/?task=<task-slug>`

Interactive API docs:

- [Swagger UI](/api/docs/)
- OpenAPI schema: `/api/schema/`

API examples:

```bash
curl -X POST http://127.0.0.1:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"owner\",\"password\":\"secret123\"}"
```

```bash
curl http://127.0.0.1:8000/api/tasks/?project=backend\&status=todo\&ordering=-created_at \
  -H "Authorization: Bearer <access-token>"
```

```bash
curl -X PATCH http://127.0.0.1:8000/api/workspaces/engineering/projects/backend/tasks/ship-api/ \
  -H "Authorization: Bearer <access-token>" \
  -H "Content-Type: application/json" \
  -d "{\"description\":\"Updated from API\"}"
```

## Testing

Run the service and API tests with:

```bash
python manage.py test workspaces tasks comments api
```
