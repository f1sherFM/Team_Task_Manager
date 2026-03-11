You are a senior Django backend engineer.

Your task is to design and implement a production-like Django project called **Team Task Manager (TTM)**.

The project is a SaaS application for team-based project and task management (similar to Trello / Asana but simplified).

The goal of this project is to serve as a strong backend portfolio project.

Focus on:
- clean architecture
- readable code
- proper domain modeling
- centralized business logic
- separation of concerns

------------------------------------------------
STACK
------------------------------------------------

Python 3.12+
Django 5.x
Django REST Framework (latest stable)
PostgreSQL 15+

The project must be compatible with deployment on Render.

Database configuration must use DATABASE_URL.

------------------------------------------------
FRONTEND POLICY
------------------------------------------------

HTML pages are minimal and server-rendered.

They exist only as a simple functional interface.

The primary focus of the project is backend architecture and domain logic, not advanced frontend development.

Do NOT build complex UI components.

------------------------------------------------
ARCHITECTURE PRINCIPLES
------------------------------------------------

The project must follow a clear domain architecture.

selectors handle read/query use cases.

services handle state changes and business workflows.

Business rules live in services and permission helpers.

Selectors are responsible only for read/query logic.

Views, forms and serializers must remain thin.

------------------------------------------------
ARCHITECTURE RULES
------------------------------------------------

All write operations must go through services.

Selectors are responsible only for read/query logic.

Business rules live in services and permission helpers.

Permission helpers live in core.permissions.

Permissions must never be implemented directly in views or serializers.

Views, forms and serializers must remain thin.

Use transaction.atomic() for multi-step mutations.

Avoid fat models and duplicated validation.

------------------------------------------------
PROJECT STRUCTURE
------------------------------------------------

Create Django project:

team_task_manager

Create apps:

accounts
workspaces
projects
tasks
comments
activity
api
core

Responsibilities:

accounts
- user profile
- authentication pages

workspaces
- workspace
- membership
- invitations

projects
- projects inside workspaces

tasks
- tasks
- status
- priority
- assignee

comments
- comments for tasks

activity
- activity log

api
- DRF endpoints

core
- selectors
- services
- permission helpers
- slug utilities
- shared helpers

------------------------------------------------
DOMAIN MODELS
------------------------------------------------

Use the default Django User model.

Profile extends user information.

Profile
- user
- avatar
- bio
- created_at

Workspace
- name
- slug
- owner
- created_at
- updated_at

Membership
- workspace
- user
- role (owner / admin / member)
- joined_at

UniqueConstraint(workspace, user)

Invitation
- workspace
- email
- role
- token
- invited_by
- created_at
- expires_at
- accepted_at

Project
- workspace
- name
- slug
- description
- created_by
- created_at
- updated_at
- is_archived

Task
- project
- title
- slug
- description
- status (todo / in_progress / done)
- priority (low / medium / high)
- created_by
- assignee
- due_date
- created_at
- updated_at

Comment
- task
- author
- text
- created_at
- updated_at
- is_deleted

ActivityLog
- workspace
- actor
- action
- target_type
- target_id
- metadata (JSONField)
- created_at

------------------------------------------------
SLUG POLICY
------------------------------------------------

Workspace.slug must be globally unique.

Project.slug must be unique within a workspace.

Task.slug must be unique within a project.

Slugs are automatically generated on creation.

Slugs are immutable after creation.

------------------------------------------------
WORKSPACE OWNERSHIP
------------------------------------------------

Workspace.owner is the canonical owner.

Owner must always also have Membership with role=owner.

Workspace must always have exactly one owner membership.

Owner membership cannot be removed while the workspace exists.

Membership roles:

owner
admin
member

------------------------------------------------
INVITATION RULES
------------------------------------------------

Invitation rules:

- invitations are unique per workspace/email
- invitations cannot be created for existing members
- invitation tokens are single-use
- expired invitations cannot be accepted
- accepting an invitation creates a membership with the invited role
- accepted_at must be set when invitation is accepted

------------------------------------------------
COMMENT SOFT DELETE
------------------------------------------------

Comments support soft delete.

Rules:

- deleted comments are displayed as "[deleted]"
- original comment text must not be returned in UI or API
- only the comment author or workspace admin/owner can delete comments
- deleted comments remain visible in the activity log

------------------------------------------------
TRANSACTION POLICY
------------------------------------------------

Multi-model write operations must use transaction.atomic() inside services.

------------------------------------------------
DOMAIN ACCESS MODEL
------------------------------------------------

Membership is the central access model.

Access chain:

User → Membership → Workspace → Project → Task

Rules:

- only workspace members can see projects and tasks
- owner/admin can create projects
- workspace members can create tasks
- owner/admin can assign tasks
- task status can be changed by owner/admin or assignee
- comments are available only to workspace members

------------------------------------------------
IMPLEMENTATION PLAN
------------------------------------------------

Implement the project step by step.

Do NOT skip steps.

Each step must be complete before moving forward.

--------------------------------
STEP 1 — PROJECT BOOTSTRAP
--------------------------------

1. create Django project `team_task_manager`
2. create all apps
3. register apps in settings
4. configure PostgreSQL using DATABASE_URL
5. configure templates
6. configure static files
7. create base.html
8. enable Django authentication
9. create requirements.txt or pyproject.toml

--------------------------------
STEP 2 — USER PROFILE
--------------------------------

1. implement Profile model
2. create signal to auto-create Profile
3. configure Django admin
4. create pages:
   - signup
   - login
   - logout

--------------------------------
STEP 3 — WORKSPACE DOMAIN
--------------------------------

1. implement Workspace model
2. implement Membership model
3. implement roles
4. add UniqueConstraint
5. implement Invitation model
6. configure admin

--------------------------------
STEP 4 — WORKSPACE HTML
--------------------------------

Create pages:

/workspaces/
/workspaces/create/
/workspaces/<slug>/
/workspaces/<slug>/members/

Features:

- workspace creation
- list of user workspaces
- list of workspace members

--------------------------------
STEP 5 — PROJECTS
--------------------------------

Implement Project model.

Pages:

/workspaces/<slug>/projects/
/projects/<slug>/

Rules:

- projects belong to workspace
- only workspace members can see them

--------------------------------
STEP 6 — TASKS
--------------------------------

Implement Task model.

Pages:

/projects/<slug>/tasks/
/tasks/<slug>/
/tasks/<slug>/edit/

Features:

- create tasks
- assign assignee
- change task status

--------------------------------
STEP 7 — COMMENTS
--------------------------------

Implement Comment model.

Features:

- task comments
- soft delete

--------------------------------
STEP 8 — ACTIVITY LOG
--------------------------------

Implement ActivityLog model.

Events:

task_created
task_assigned
task_status_changed
comment_added

Activity log must be written via services.

--------------------------------
STEP 9 — API
--------------------------------

Integrate:

Django REST Framework
JWT authentication

Endpoints:

/api/auth/token/
/api/auth/token/refresh/

workspaces
projects
tasks
comments
activity

Serializers validate input and delegate mutations to services.

DRF permissions must call centralized permission helpers.

API and HTML must reuse the same domain logic.

--------------------------------
STEP 10 — PERFORMANCE
--------------------------------

Implement:

selectors
permission helpers

Use:

select_related
prefetch_related
pagination

--------------------------------
STEP 11 — TESTING
--------------------------------

Testing strategy:

Prefer service-level and API-level tests.

Focus on permission boundaries and core workflows.

Tests should cover:

workspace access
membership roles
task creation
task assignment
status change permissions
comments
API permissions

--------------------------------
STEP 12 — PROJECT INFRASTRUCTURE
--------------------------------

Add:

.env
.env.example
requirements.txt or pyproject.toml
ruff
optional black

--------------------------------
STEP 13 — README
--------------------------------

README must include:

- project overview
- architecture explanation
- quick start
- PostgreSQL setup
- API endpoints
- project structure

------------------------------------------------
IMPORTANT
------------------------------------------------

Do NOT implement at the beginning:

- websocket
- realtime updates
- drag-and-drop kanban board
- email notifications
- file attachments
- notification center

First build a solid backend core.

------------------------------------------------
FINAL STEP
------------------------------------------------

After generating code:

1. explain the project structure
2. highlight important files
3. explain where domain logic lives

------------------------------------------------
GIT WORKFLOW
------------------------------------------------

The project must be generated as a sequence of logical git commits.

Each implementation step must correspond to one commit.

Commit messages must follow this style:

feat: bootstrap Django project
feat: implement user profile
feat: workspace domain models
feat: workspace HTML pages
feat: project domain
feat: task domain
feat: task comments
feat: activity log
feat: DRF API
feat: performance selectors
test: add core workflow tests
chore: infrastructure and linting
docs: README

For each step:

1. show the files that were created or modified
2. show the commit message
3. then continue with the next step

Do not generate the entire project in one block.

Generate it step-by-step following the implementation plan.