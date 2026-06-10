# Contributing

Thanks for contributing to Team Task Manager.

This project is backend-first and intentionally structured around a clear domain architecture.
Please preserve that structure when proposing changes.

## Development Principles

- All write operations go through services.
- Selectors are read-only query helpers.
- Permission rules live in `core.permissions`.
- Views, forms, and serializers should remain thin.
- Multi-step mutations should use `transaction.atomic()`.

## Local Setup

TTM is PostgreSQL-first in local development. SQLite fallback is supported for quick demos, but normal development and CI should target PostgreSQL.

Recommended Windows flow:

1. Copy environment variables:

```bash
copy .env.example .env
```

2. Configure PostgreSQL in `.env`.
3. Bootstrap the local environment:

```bash
bootstrap_ttm_local.cmd
```

4. Optional demo data:

```bash
seed_ttm_demo.cmd
```

5. Run checks:

```bash
lint_ttm_local.cmd
test_ttm_local.cmd
check_ttm_integrity.cmd
```

Manual flow:

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy environment variables:

```bash
copy .env.example .env
```

4. Configure at least:

```env
DJANGO_SECRET_KEY=change-me
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/team_task_manager
DB_SSL_REQUIRE=False
```

5. Run migrations:

```bash
python manage.py migrate
```

6. Run the test suite:

```bash
python manage.py test
```

7. Run linting:

```bash
python -m ruff check .
```

8. Run deployment-oriented checks before opening a PR:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py check_domain_integrity
```

## Coding Expectations

- Keep domain logic in app services such as `workspaces/services.py`, `projects/services.py`, `tasks/services.py`, and `comments/services.py`.
- Reuse existing selectors instead of embedding access filtering in views or serializers.
- Add or update tests for every behavior change, especially around permissions and workflows.
- Prefer small, reviewable commits with clear messages.
- Do not mutate slugs after object creation.
- Keep demo data and integrity tooling deterministic so local smoke checks stay trustworthy.

## Pull Requests

When opening a pull request, please include:

- a short summary of the change
- the affected user or API behavior
- notes about permissions, migrations, or backward compatibility
- test coverage details

GitHub Actions will run linting, Django checks, migration drift checks, PostgreSQL-backed tests, and coverage reporting.

Good PR examples for this repository:

- `feat: add workspace invitations`
- `fix: block archived project task mutations`
- `test: cover invitation acceptance rules`
- `docs: update contributor guide`

## Areas That Need Extra Care

- workspace ownership invariants
- invitation acceptance and membership creation
- archived project read-only rules
- reuse of shared permission helpers
- API and HTML parity when they share the same domain workflow
