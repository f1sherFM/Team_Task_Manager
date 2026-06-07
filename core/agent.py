import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from django.contrib.auth import get_user_model
from django.utils.dateparse import parse_date
from django.utils.text import slugify

from core.exceptions import DomainError
from projects.models import Project
from projects.selectors import get_workspace_projects
from projects.services import create_project
from tasks.models import TaskPriority, TaskStatus
from tasks.selectors import get_project_tasks
from tasks.services import UNSET, create_task, update_task
from workspaces.models import Membership, Workspace
from workspaces.selectors import get_user_workspaces

User = get_user_model()


@dataclass(frozen=True)
class AgentParsedRequest:
    action: str
    workspace: str | None = None
    project: str | None = None
    task: str | None = None
    title: str | None = None
    name: str | None = None
    description: str = ""
    priority: str | None = None
    due_date: date | None = None
    assignee: str | None = None
    status: str | None = None


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


def list_tasks_for_agent(*, actor_ref: str, workspace_ref: str, project_ref: str) -> list[dict]:
    actor = resolve_actor(actor_ref=actor_ref)
    workspace = resolve_workspace(actor=actor, workspace_ref=workspace_ref)
    project = resolve_project(actor=actor, workspace=workspace, project_ref=project_ref)
    tasks = get_project_tasks(project=project).order_by("created_at")
    return [
        {
            "slug": task.slug,
            "title": task.title,
            "status": task.status,
            "priority": task.priority,
            "assignee": task.assignee.username if task.assignee else None,
        }
        for task in tasks
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
    priority: str | None = None,
    due_date: date | str | None = None,
    assignee_ref: str | None = None,
    status: str | None = None,
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
    effective_priority = priority or TaskPriority.MEDIUM
    effective_status = status or TaskStatus.TODO

    task = create_task(
        project=project,
        title=title,
        description=description,
        priority=effective_priority,
        due_date=due_date_value,
        assignee=assignee,
        created_by=actor,
    )
    if effective_status != TaskStatus.TODO:
        task = update_task(task=task, actor=actor, status=effective_status)
    return task


def update_task_for_agent(
    *,
    actor_ref: str,
    workspace_ref: str,
    project_ref: str,
    task_ref: str,
    title: str | None = None,
    description: str | None = None,
    priority: str | None = None,
    due_date: date | str | None = None,
    assignee_ref: str | None = None,
    status: str | None = None,
):
    actor = resolve_actor(actor_ref=actor_ref)
    workspace = resolve_workspace(actor=actor, workspace_ref=workspace_ref)
    project = resolve_project(actor=actor, workspace=workspace, project_ref=project_ref)
    task = resolve_task(project=project, task_ref=task_ref)

    assignee = UNSET
    if assignee_ref is not None:
        assignee = (
            resolve_workspace_user(workspace=workspace, user_ref=assignee_ref)
            if assignee_ref
            else None
        )

    due_date_value = UNSET
    if due_date is not None:
        due_date_value = parse_optional_date(due_date) if isinstance(due_date, str) else due_date

    return update_task(
        task=task,
        actor=actor,
        title=title if title is not None else UNSET,
        description=description if description is not None else UNSET,
        priority=priority if priority is not None else UNSET,
        due_date=due_date_value,
        assignee=assignee,
        status=status if status is not None else UNSET,
    )


def close_task_for_agent(
    *,
    actor_ref: str,
    workspace_ref: str,
    project_ref: str,
    task_ref: str,
):
    return update_task_for_agent(
        actor_ref=actor_ref,
        workspace_ref=workspace_ref,
        project_ref=project_ref,
        task_ref=task_ref,
        status=TaskStatus.DONE,
    )


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

    if parsed_request.action == "create_task":
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
        return _task_payload(action=parsed_request.action, task=task)

    if not parsed_request.workspace or not parsed_request.project or not parsed_request.task:
        raise DomainError("Task update requests require workspace, project, and task.")

    if parsed_request.action == "close_task":
        task = close_task_for_agent(
            actor_ref=actor_ref,
            workspace_ref=parsed_request.workspace,
            project_ref=parsed_request.project,
            task_ref=parsed_request.task,
        )
    else:
        task = update_task_for_agent(
            actor_ref=actor_ref,
            workspace_ref=parsed_request.workspace,
            project_ref=parsed_request.project,
            task_ref=parsed_request.task,
            title=parsed_request.title,
            description=parsed_request.description or None,
            priority=parsed_request.priority,
            due_date=parsed_request.due_date,
            assignee_ref=parsed_request.assignee,
            status=parsed_request.status,
        )
    return _task_payload(action=parsed_request.action, task=task)


def preview_agent_request(*, actor_ref: str, request_text: str) -> dict:
    return _preview_agent_request(
        actor_ref=actor_ref,
        request_text=request_text,
        planned_projects={},
    )


def _preview_agent_request(
    *,
    actor_ref: str,
    request_text: str,
    planned_projects: dict[tuple[str, str], str],
) -> dict:
    actor = resolve_actor(actor_ref=actor_ref)
    parsed_request = parse_agent_request(request_text=request_text)
    payload = {
        "action": parsed_request.action,
        "actor": actor.username,
        "workspace": parsed_request.workspace,
        "project": parsed_request.project,
        "task": parsed_request.task,
        "title": parsed_request.title,
        "name": parsed_request.name,
        "description": parsed_request.description,
        "priority": parsed_request.priority,
        "due_date": parsed_request.due_date.isoformat() if parsed_request.due_date else None,
        "assignee": parsed_request.assignee,
        "status": parsed_request.status,
    }

    workspace = None
    if parsed_request.workspace:
        workspace = resolve_workspace(actor=actor, workspace_ref=parsed_request.workspace)
        payload["workspace_slug"] = workspace.slug

    if parsed_request.action == "create_project" and workspace and parsed_request.name:
        project_slug = slugify(parsed_request.name)
        planned_projects[(workspace.slug, parsed_request.name.casefold())] = project_slug
        planned_projects[(workspace.slug, project_slug.casefold())] = project_slug
        payload["project_slug"] = project_slug

    project = None
    if parsed_request.workspace and parsed_request.project:
        if workspace is None:
            workspace = resolve_workspace(actor=actor, workspace_ref=parsed_request.workspace)
        project_slug = planned_projects.get((workspace.slug, parsed_request.project.casefold()))
        if project_slug is None:
            project = resolve_project(
                actor=actor,
                workspace=workspace,
                project_ref=parsed_request.project,
            )
            project_slug = project.slug
        payload["project_slug"] = project_slug
        if project is None and project_slug == parsed_request.project:
            project = resolve_project(
                actor=actor,
                workspace=workspace,
                project_ref=project_slug,
            )

    if parsed_request.workspace and parsed_request.task:
        if workspace is None or parsed_request.project is None:
            raise DomainError("Task previews require workspace and project.")
        if project is None:
            project_ref = payload.get("project_slug") or parsed_request.project
            project = resolve_project(actor=actor, workspace=workspace, project_ref=project_ref)
        task = resolve_task(project=project, task_ref=parsed_request.task)
        payload["task_slug"] = task.slug

    if parsed_request.workspace and parsed_request.assignee:
        if workspace is None:
            workspace = resolve_workspace(actor=actor, workspace_ref=parsed_request.workspace)
        assignee = resolve_workspace_user(workspace=workspace, user_ref=parsed_request.assignee)
        payload["assignee_username"] = assignee.username
    return payload


def execute_agent_batch_request(
    *,
    actor_ref: str,
    request_text: str,
    preview: bool = False,
) -> list[dict]:
    request_chunks = expand_agent_request_text(request_text=request_text)
    if not request_chunks:
        raise DomainError("No agent requests were found in the batch payload.")
    if preview:
        planned_projects: dict[tuple[str, str], str] = {}
        return [
            _preview_agent_request(
                actor_ref=actor_ref,
                request_text=request_chunk,
                planned_projects=planned_projects,
            )
            for request_chunk in request_chunks
        ]
    return [
        execute_agent_request(actor_ref=actor_ref, request_text=request_chunk)
        for request_chunk in request_chunks
    ]


def execute_agent_file_request(
    *,
    actor_ref: str,
    file_path: str,
    preview: bool = False,
) -> list[dict]:
    path = Path(file_path).expanduser()
    if not path.exists():
        raise DomainError(f'Agent request file "{file_path}" was not found.')
    if not path.is_file():
        raise DomainError(f'Agent request path "{file_path}" is not a file.')
    request_text = path.read_text(encoding="utf-8")
    return execute_agent_batch_request(
        actor_ref=actor_ref,
        request_text=request_text,
        preview=preview,
    )


def parse_agent_request(*, request_text: str) -> AgentParsedRequest:
    normalized_request = request_text.lstrip("\ufeff").strip()
    lower_request = normalized_request.lower()
    mapping = _parse_key_value_request(normalized_request)

    action = mapping.get("action") or _infer_action(lower_request)
    if action not in {"create_project", "create_task", "update_task", "close_task"}:
        raise DomainError("Could not determine which automation action to run.")

    workspace = mapping.get("workspace") or _extract_quoted_value(
        normalized_request,
        keywords=("workspace", "workspace_slug"),
    )
    project = mapping.get("project") or _extract_quoted_value(
        normalized_request,
        keywords=("project", "project_slug"),
    )
    task = mapping.get("task") or _extract_quoted_value(
        normalized_request,
        keywords=("task", "task_slug"),
    )
    title = mapping.get("title") or _extract_quoted_value(
        normalized_request,
        keywords=("title",),
    )
    name = mapping.get("name") or _extract_quoted_value(
        normalized_request,
        keywords=("project", "name"),
    )
    description = mapping.get("description", "")
    priority = mapping.get("priority")
    due_date = parse_optional_date(mapping.get("due_date"))
    assignee = mapping.get("assignee")
    status = mapping.get("status")

    if action == "create_task" and priority is None:
        priority = TaskPriority.MEDIUM
    if action == "create_task" and status is None:
        status = TaskStatus.TODO
    if action == "close_task":
        status = TaskStatus.DONE
    if priority is not None:
        validate_priority(priority)
    if status is not None:
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
        task=task,
        title=title,
        description=description,
        priority=priority,
        due_date=due_date,
        assignee=assignee,
        status=status,
    )


def split_batch_request(*, request_text: str) -> list[str]:
    chunks = [
        chunk.strip()
        for chunk in re.split(r"\n\s*---+\s*\n", request_text.strip())
        if chunk.strip()
    ]
    return chunks


def expand_agent_request_text(*, request_text: str) -> list[str]:
    batch_chunks = split_batch_request(request_text=request_text)
    if len(batch_chunks) > 1:
        return batch_chunks

    markdown_chunks = parse_markdown_brief(request_text=request_text)
    if markdown_chunks:
        return markdown_chunks

    single_chunk = request_text.strip()
    return [single_chunk] if single_chunk else []


def parse_markdown_brief(*, request_text: str) -> list[str]:
    lines = request_text.lstrip("\ufeff").splitlines()
    metadata: dict[str, str] = {}
    task_chunks: list[dict[str, str]] = []
    current_task: dict[str, str] | None = None
    saw_task_bullet = False

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            continue

        heading_match = re.match(r"^#{1,6}\s*(.+)$", stripped)
        if heading_match:
            stripped = heading_match.group(1).strip()

        bullet_match = re.match(r"^[-*]\s*(?:\[(?P<state>[ xX])\]\s*)?(?P<title>.*)$", stripped)
        if bullet_match and bullet_match.group("title").strip():
            saw_task_bullet = True
            current_task = {"title": bullet_match.group("title").strip()}
            if bullet_match.group("state") and bullet_match.group("state").lower() == "x":
                current_task["status"] = TaskStatus.DONE
            task_chunks.append(current_task)
            continue

        if ":" not in stripped:
            continue

        key, value = stripped.split(":", 1)
        normalized_key = key.strip().lower().replace(" ", "_")
        cleaned_value = value.strip()

        if current_task is not None and normalized_key in {
            "description",
            "priority",
            "assignee",
            "due_date",
            "status",
            "task",
            "action",
        }:
            current_task[normalized_key] = cleaned_value
            continue

        if normalized_key in {
            "workspace",
            "project",
            "action",
            "task_action",
            "name",
            "description",
        }:
            metadata[normalized_key] = cleaned_value

    if not saw_task_bullet:
        return []

    chunks: list[str] = []
    if metadata.get("action") == "create_project":
        workspace = metadata.get("workspace")
        project_name = metadata.get("project") or metadata.get("name")
        if workspace and project_name:
            project_lines = [
                "action: create_project",
                f"workspace: {workspace}",
                f"name: {project_name}",
            ]
            if metadata.get("description"):
                project_lines.append(f"description: {metadata['description']}")
            chunks.append("\n".join(project_lines))

    default_task_action = metadata.get("task_action", "create_task")
    for task_chunk in task_chunks:
        task_action = task_chunk.get("action", default_task_action)
        task_lines = [
            f"action: {task_action}",
            f"workspace: {metadata.get('workspace', '')}",
            f"project: {metadata.get('project', metadata.get('name', ''))}",
        ]
        if task_action == "create_task":
            task_lines.append(f"title: {task_chunk['title']}")
        else:
            task_reference = task_chunk.get("task", task_chunk["title"])
            task_lines.append(f"task: {task_reference}")
            if task_chunk["title"] != task_reference:
                task_lines.append(f"title: {task_chunk['title']}")
        for field_name in ("description", "priority", "assignee", "due_date", "status"):
            field_value = task_chunk.get(field_name)
            if field_value:
                task_lines.append(f"{field_name}: {field_value}")
        chunks.append("\n".join(task_lines))

    valid_chunks: list[str] = []
    for chunk in chunks:
        if "workspace: " not in chunk:
            continue
        if "action: create_project" in chunk and "name: " in chunk:
            valid_chunks.append(chunk)
            continue
        if "action: create_task" in chunk and "project: " in chunk and "title: " in chunk:
            valid_chunks.append(chunk)
            continue
        if (
            ("action: update_task" in chunk or "action: close_task" in chunk)
            and "project: " in chunk
            and "task: " in chunk
        ):
            valid_chunks.append(chunk)
    return valid_chunks


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


def resolve_task(*, project: Project, task_ref: str):
    queryset = get_project_tasks(project=project)
    task_ref = task_ref.strip()
    task = queryset.filter(slug=task_ref).first()
    if task is None:
        task = queryset.filter(title__iexact=task_ref).first()
    if task is not None:
        return task

    matches = list(queryset.filter(title__icontains=task_ref).order_by("created_at")[:2])
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise DomainError(f'Task reference "{task_ref}" is ambiguous.')
    raise DomainError(f'Task "{task_ref}" was not found in project "{project.slug}".')


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
        normalized_key = key.strip().lstrip("\ufeff").lower().replace(" ", "_")
        cleaned_value = value.strip().strip('"').strip("'")
        if cleaned_value:
            mapping[normalized_key] = cleaned_value
    return mapping


def _infer_action(lower_request: str) -> str:
    task_markers = ("create task", "add task", "new task")
    project_markers = ("create project", "add project", "new project")
    update_task_markers = ("update task", "edit task")
    close_task_markers = ("close task", "complete task", "done task")
    if any(marker in lower_request for marker in task_markers):
        return "create_task"
    if any(marker in lower_request for marker in project_markers):
        return "create_project"
    if any(marker in lower_request for marker in update_task_markers):
        return "update_task"
    if any(marker in lower_request for marker in close_task_markers):
        return "close_task"
    return ""


def _extract_quoted_value(request_text: str, *, keywords: tuple[str, ...]) -> str | None:
    for keyword in keywords:
        pattern = rf"{re.escape(keyword)}\s*[=:]?\s*[\"']([^\"']+)[\"']"
        match = re.search(pattern, request_text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def _task_payload(*, action: str, task) -> dict:
    return {
        "action": action,
        "workspace": task.project.workspace.slug,
        "project": task.project.slug,
        "task": task.slug,
        "title": task.title,
        "status": task.status,
    }
