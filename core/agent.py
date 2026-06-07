import re
from dataclasses import dataclass
from datetime import date

from django.contrib.auth import get_user_model
from django.utils.dateparse import parse_date

from core.exceptions import DomainError
from projects.models import Project
from projects.selectors import get_workspace_projects
from projects.services import create_project
from tasks.models import TaskPriority, TaskStatus
from tasks.services import create_task, update_task
from workspaces.models import Membership, Workspace
from workspaces.selectors import get_user_workspaces

User = get_user_model()


@dataclass(frozen=True)
class AgentParsedRequest:
    action: str
    workspace: str | None = None
    project: str | None = None
    title: str | None = None
    name: str | None = None
    description: str = ""
    priority: str = TaskPriority.MEDIUM
    due_date: date | None = None
    assignee: str | None = None
    status: str = TaskStatus.TODO


def list_workspaces_for_agent(*, actor_ref: str) -> list[dict]:
    actor = resolve_actor(actor_ref=actor_ref)
    workspaces = get_user_workspaces(actor).order_by("name")
    return [
        {
            "slug": workspace.slug,
            "name": workspace.name,
            "owner": workspace.owner.username,
        }
        for workspace in workspaces
    ]


def list_projects_for_agent(*, actor_ref: str, workspace_ref: str) -> list[dict]:
    actor = resolve_actor(actor_ref=actor_ref)
    workspace = resolve_workspace(actor=actor, workspace_ref=workspace_ref)
    projects = get_workspace_projects(workspace=workspace).order_by("name")
    return [
        {
            "slug": project.slug,
            "name": project.name,
            "is_archived": project.is_archived,
        }
        for project in projects
    ]


def create_project_for_agent(
    *,
    actor_ref: str,
    workspace_ref: str,
    name: str,
    description: str = "",
) -> Project:
    actor = resolve_actor(actor_ref=actor_ref)
    workspace = resolve_workspace(actor=actor, workspace_ref=workspace_ref)
    return create_project(
        workspace=workspace,
        name=name,
        description=description,
        created_by=actor,
    )


def create_task_for_agent(
    *,
    actor_ref: str,
    workspace_ref: str,
    project_ref: str,
    title: str,
    description: str = "",
    priority: str = TaskPriority.MEDIUM,
    due_date: date | str | None = None,
    assignee_ref: str | None = None,
    status: str = TaskStatus.TODO,
):
    actor = resolve_actor(actor_ref=actor_ref)
    workspace = resolve_workspace(actor=actor, workspace_ref=workspace_ref)
    project = resolve_project(actor=actor, workspace=workspace, project_ref=project_ref)
    assignee = (
        resolve_workspace_user(workspace=workspace, user_ref=assignee_ref)
        if assignee_ref
        else None
    )
    due_date_value = parse_optional_date(due_date) if isinstance(due_date, str) else due_date

    task = create_task(
        project=project,
        title=title,
        description=description,
        priority=priority,
        due_date=due_date_value,
        assignee=assignee,
        created_by=actor,
    )
    if status != TaskStatus.TODO:
        task = update_task(task=task, actor=actor, status=status)
    return task


def execute_agent_request(*, actor_ref: str, request_text: str) -> dict:
    parsed_request = parse_agent_request(request_text=request_text)
    if parsed_request.action == "create_project":
        if not parsed_request.workspace or not parsed_request.name:
            raise DomainError("Project requests require workspace and name.")
        project = create_project_for_agent(
            actor_ref=actor_ref,
            workspace_ref=parsed_request.workspace,
            name=parsed_request.name,
            description=parsed_request.description,
        )
        return {
            "action": parsed_request.action,
            "workspace": project.workspace.slug,
            "project": project.slug,
            "name": project.name,
        }

    if not parsed_request.workspace or not parsed_request.project or not parsed_request.title:
        raise DomainError("Task requests require workspace, project, and title.")

    task = create_task_for_agent(
        actor_ref=actor_ref,
        workspace_ref=parsed_request.workspace,
        project_ref=parsed_request.project,
        title=parsed_request.title,
        description=parsed_request.description,
        priority=parsed_request.priority,
        due_date=parsed_request.due_date,
        assignee_ref=parsed_request.assignee,
        status=parsed_request.status,
    )
    return {
        "action": parsed_request.action,
        "workspace": task.project.workspace.slug,
        "project": task.project.slug,
        "task": task.slug,
        "title": task.title,
    }


def parse_agent_request(*, request_text: str) -> AgentParsedRequest:
    normalized_request = request_text.strip()
    lower_request = normalized_request.lower()
    mapping = _parse_key_value_request(normalized_request)

    action = mapping.get("action") or _infer_action(lower_request)
    if action not in {"create_project", "create_task"}:
        raise DomainError("Could not determine whether to create a project or task.")

    workspace = mapping.get("workspace") or _extract_quoted_value(
        normalized_request,
        keywords=("workspace", "workspace_slug"),
    )
    project = mapping.get("project") or _extract_quoted_value(
        normalized_request,
        keywords=("project", "project_slug"),
    )
    title = mapping.get("title") or _extract_quoted_value(
        normalized_request,
        keywords=("task", "title"),
    )
    name = mapping.get("name") or _extract_quoted_value(
        normalized_request,
        keywords=("project", "name"),
    )
    description = mapping.get("description", "")
    priority = mapping.get("priority", TaskPriority.MEDIUM)
    due_date = parse_optional_date(mapping.get("due_date"))
    assignee = mapping.get("assignee")
    status = mapping.get("status", TaskStatus.TODO)

    validate_priority(priority)
    validate_status(status)

    if action == "create_project":
        return AgentParsedRequest(
            action=action,
            workspace=workspace,
            name=name,
            description=description,
        )

    return AgentParsedRequest(
        action=action,
        workspace=workspace,
        project=project,
        title=title,
        description=description,
        priority=priority,
        due_date=due_date,
        assignee=assignee,
        status=status,
    )


def resolve_actor(*, actor_ref: str):
    actor_ref = actor_ref.strip()
    user = User.objects.filter(username=actor_ref).first()
    if user is None:
        user = User.objects.filter(email__iexact=actor_ref).first()
    if user is None:
        raise DomainError(f'Actor "{actor_ref}" was not found.')
    return user


def resolve_workspace(*, actor, workspace_ref: str) -> Workspace:
    queryset = get_user_workspaces(actor)
    return _resolve_workspace_from_queryset(queryset=queryset, workspace_ref=workspace_ref)


def resolve_project(*, actor, workspace: Workspace, project_ref: str) -> Project:
    queryset = get_workspace_projects(workspace=workspace)
    return _resolve_project_from_queryset(queryset=queryset, project_ref=project_ref)


def resolve_workspace_user(*, workspace: Workspace, user_ref: str):
    membership = (
        Membership.objects.filter(workspace=workspace, user__username=user_ref)
        .select_related("user")
        .first()
    )
    if membership is None:
        membership = (
            Membership.objects.filter(workspace=workspace, user__email__iexact=user_ref)
            .select_related("user")
            .first()
        )
    if membership is None:
        raise DomainError(f'Workspace user "{user_ref}" was not found.')
    return membership.user


def validate_priority(priority: str) -> None:
    valid_priorities = {choice for choice, _ in TaskPriority.choices}
    if priority not in valid_priorities:
        raise DomainError(f'Unsupported priority "{priority}".')


def validate_status(status: str) -> None:
    valid_statuses = {choice for choice, _ in TaskStatus.choices}
    if status not in valid_statuses:
        raise DomainError(f'Unsupported status "{status}".')


def parse_optional_date(raw_value: str | None) -> date | None:
    if not raw_value:
        return None
    parsed = parse_date(raw_value)
    if parsed is None:
        raise DomainError(f'Could not parse due_date "{raw_value}". Use YYYY-MM-DD.')
    return parsed


def _resolve_workspace_from_queryset(*, queryset, workspace_ref: str) -> Workspace:
    workspace_ref = workspace_ref.strip()
    workspace = queryset.filter(slug=workspace_ref).first()
    if workspace is None:
        workspace = queryset.filter(name__iexact=workspace_ref).first()
    if workspace is not None:
        return workspace

    matches = list(queryset.filter(name__icontains=workspace_ref).order_by("name")[:2])
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise DomainError(f'Workspace reference "{workspace_ref}" is ambiguous.')
    raise DomainError(f'Workspace "{workspace_ref}" was not found for this actor.')


def _resolve_project_from_queryset(*, queryset, project_ref: str) -> Project:
    project_ref = project_ref.strip()
    project = queryset.filter(slug=project_ref).first()
    if project is None:
        project = queryset.filter(name__iexact=project_ref).first()
    if project is not None:
        return project

    matches = list(queryset.filter(name__icontains=project_ref).order_by("name")[:2])
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise DomainError(f'Project reference "{project_ref}" is ambiguous.')
    workspace_slug = queryset.first().workspace.slug if queryset.exists() else "unknown"
    raise DomainError(
        f'Project "{project_ref}" was not found in workspace "{workspace_slug}".'
    )


def _parse_key_value_request(request_text: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for raw_line in request_text.splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        normalized_key = key.strip().lower().replace(" ", "_")
        cleaned_value = value.strip().strip('"').strip("'")
        if cleaned_value:
            mapping[normalized_key] = cleaned_value
    return mapping


def _infer_action(lower_request: str) -> str:
    task_markers = (
        "create task",
        "add task",
        "new task",
    )
    project_markers = (
        "create project",
        "add project",
        "new project",
    )
    if any(marker in lower_request for marker in task_markers):
        return "create_task"
    if any(marker in lower_request for marker in project_markers):
        return "create_project"
    return ""


def _extract_quoted_value(request_text: str, *, keywords: tuple[str, ...]) -> str | None:
    for keyword in keywords:
        pattern = rf"{re.escape(keyword)}\s*[=:]?\s*[\"']([^\"']+)[\"']"
        match = re.search(pattern, request_text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None
