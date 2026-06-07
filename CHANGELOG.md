# Changelog

All notable changes to Team Task Manager are documented in this file.

The format loosely follows Keep a Changelog and uses repository-oriented release notes
for notable implementation milestones.

## [Unreleased]

### Added
- Workspace invitation flows in HTML and API, including invitation acceptance by token.
- Project archive and unarchive workflows in services, HTML pages, and DRF endpoints.
- Read-only enforcement for archived projects across task and comment mutations.
- Additional service-level and API-level tests for invitations, archive permissions, and archived project restrictions.
- Invitation acceptance template at `templates/workspaces/invitation_accept.html`.

### Changed
- Workspace ownership rules now prevent assigning the `owner` role after workspace creation.
- Task HTML editing now updates full task details through the shared task service workflow.
- README now documents invitation and archive endpoints and the archived project behavior.
- Code style was normalized to pass `ruff check .`.

### Fixed
- Invitation acceptance now validates the invited email against the authenticated user.
- Archived projects no longer allow task creation, task updates, assignment changes, status changes, or comment mutations.
- Render deployment section in the README no longer points at broken absolute local paths.
