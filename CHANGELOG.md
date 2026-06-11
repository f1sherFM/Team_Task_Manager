# Changelog

All notable changes to Team Task Manager are documented in this file.

The format loosely follows Keep a Changelog and uses repository-oriented release notes
for notable implementation milestones.

## [Unreleased]

### Added
- Richer API filtering and search for projects, tasks, comments, and activity feeds.
- Bulk task update API endpoint for project-scoped backlog maintenance.
- `coverage_ttm_local.cmd` for local coverage execution with the same floor enforced in CI.
- Postgres-first local operational tooling with Windows-friendly helper scripts for bootstrap, linting, tests, demo seeding, and integrity checks.
- `seed_demo_data` management command for deterministic local demo environments.
- `check_domain_integrity` management command for owner, invitation, task assignment, and deleted-comment invariants.
- Structured logging baseline with stable workspace, project, task, user, and action context fields.
- Workspace invitation flows in HTML and API, including invitation acceptance by token.
- Project archive and unarchive workflows in services, HTML pages, and DRF endpoints.
- Read-only enforcement for archived projects across task and comment mutations.
- Additional service-level and API-level tests for invitations, archive permissions, and archived project restrictions.
- Invitation acceptance template at `templates/workspaces/invitation_accept.html`.
- `/healthz/` and `/readyz/` operational endpoints for liveness and readiness checks.
- GitHub Actions CI workflow for linting, Django checks, migration drift checks, and tests.
- Local agent automation commands for listing workspaces and projects and creating projects or tasks through Django services.
- Agent capture requests now support preview mode and batch execution for safer Codex-driven automation.
- Added file-based agent automation so local briefs can be previewed and applied directly.
- Added markdown checklist parsing for project briefs and task imports.
- Agent automation now supports listing tasks and updating or closing existing tasks.
- Markdown briefs can now drive maintenance flows for existing tasks via `Task Action: update_task`.
- Added Russian aliases for structured and markdown automation requests.
- Added a repo-side MCP server for Codex, including native tools for workspace, member, project, and task automation.

### Changed
- API list endpoints now support stronger selector-driven query contracts instead of ad hoc view filtering.
- Task API now supports mass update workflows for shared status and assignment changes.
- `seed_demo_data` now supports `--reset` for rebuilding the demo baseline from scratch.
- Domain integrity checks now validate project/task creators, comment authors, owner-role invitations, and late invitation acceptance.
- Coverage reporting now enforces an `85%` floor in CI.
- GitHub Actions CI is now split into `lint`, `django-check`, `tests`, and `coverage` jobs, with PostgreSQL-backed test execution and a coverage artifact.
- Local bootstrap no longer depends exclusively on the `py` launcher and can fall back to the bundled Codex Python runtime.
- Workspace ownership rules now prevent assigning the `owner` role after workspace creation.
- Task HTML editing now updates full task details through the shared task service workflow.
- README now documents invitation and archive endpoints and the archived project behavior.
- Code style was normalized to pass `ruff check .`.
- Render health checks now target `/healthz/` instead of the home page.

### Fixed
- Invitation acceptance now validates the invited email against the authenticated user.
- Archived projects no longer allow task creation, task updates, assignment changes, status changes, or comment mutations.
- Render deployment section in the README no longer points at broken absolute local paths.
