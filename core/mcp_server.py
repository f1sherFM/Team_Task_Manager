import os
import sys
from pathlib import Path

import django
from asgiref.sync import sync_to_async
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

REPO_ROOT = Path(__file__).resolve().parent.parent

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

load_dotenv(REPO_ROOT / ".env")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "team_task_manager.settings")
django.setup()

from core.agent import (  # noqa: E402
    close_task_for_agent,
    create_project_for_agent,
    create_task_for_agent,
    execute_agent_batch_request,
    execute_agent_file_request,
    list_members_for_agent,
    list_projects_for_agent,
    list_tasks_for_agent,
    list_workspaces_for_agent,
    update_task_for_agent,
)
from core.exceptions import DomainError  # noqa: E402

server = FastMCP(
    name="TTM Agent Tools",
    instructions=(
        "Use these tools to manage Team Task Manager workspaces, projects, and tasks "
        "through Django domain services instead of browser clicks or raw API calls."
    ),
)


def resolve_actor_ref(actor_ref: str | None) -> str:
    if actor_ref:
        return actor_ref
    default_actor = os.environ.get("TTM_AGENT_DEFAULT_ACTOR", "").strip()
    if default_actor:
        return default_actor
    raise ValueError(
        "No actor was provided. Set TTM_AGENT_DEFAULT_ACTOR in the plugin config or pass actor_ref."
    )


def _domain_error(exc: DomainError) -> ValueError:
    return ValueError(str(exc))


async def run_agent_sync(callable_obj, /, **kwargs):
    try:
        return await sync_to_async(callable_obj, thread_sensitive=True)(**kwargs)
    except DomainError as exc:
        raise _domain_error(exc) from exc


@server.tool(
    name="ttm_get_context",
    description=(
        "Show the repo root and default actor used by the Team Task Manager "
        "automation tools."
    ),
)
def ttm_get_context() -> dict:
    return {
        "repo_root": str(REPO_ROOT),
        "default_actor": os.environ.get("TTM_AGENT_DEFAULT_ACTOR"),
    }


@server.tool(
    name="ttm_list_workspaces",
    description="List workspaces the actor can access.",
)
async def ttm_list_workspaces(actor_ref: str | None = None) -> list[dict]:
    return await run_agent_sync(
        list_workspaces_for_agent,
        actor_ref=resolve_actor_ref(actor_ref),
    )


@server.tool(
    name="ttm_list_projects",
    description="List projects in a workspace the actor can access.",
)
async def ttm_list_projects(workspace_ref: str, actor_ref: str | None = None) -> list[dict]:
    return await run_agent_sync(
        list_projects_for_agent,
        actor_ref=resolve_actor_ref(actor_ref),
        workspace_ref=workspace_ref,
    )


@server.tool(
    name="ttm_list_members",
    description="List members in a workspace so Codex can choose valid assignees and admins.",
)
async def ttm_list_members(workspace_ref: str, actor_ref: str | None = None) -> list[dict]:
    return await run_agent_sync(
        list_members_for_agent,
        actor_ref=resolve_actor_ref(actor_ref),
        workspace_ref=workspace_ref,
    )


@server.tool(
    name="ttm_list_tasks",
    description="List tasks in a project, including assignee, status, and priority.",
)
async def ttm_list_tasks(
    workspace_ref: str,
    project_ref: str,
    actor_ref: str | None = None,
) -> list[dict]:
    return await run_agent_sync(
        list_tasks_for_agent,
        actor_ref=resolve_actor_ref(actor_ref),
        workspace_ref=workspace_ref,
        project_ref=project_ref,
    )


@server.tool(
    name="ttm_create_project",
    description="Create a project inside a workspace using the project's Django services.",
)
async def ttm_create_project(
    workspace_ref: str,
    name: str,
    description: str = "",
    actor_ref: str | None = None,
) -> dict:
    project = await run_agent_sync(
        create_project_for_agent,
        actor_ref=resolve_actor_ref(actor_ref),
        workspace_ref=workspace_ref,
        name=name,
        description=description,
    )
    return {
        "workspace": project.workspace.slug,
        "project": project.slug,
        "name": project.name,
    }


@server.tool(
    name="ttm_create_task",
    description=(
        "Create a task in a project. Use list_members first when you need a "
        "valid assignee."
    ),
)
async def ttm_create_task(
    workspace_ref: str,
    project_ref: str,
    title: str,
    description: str = "",
    priority: str | None = None,
    due_date: str | None = None,
    assignee_ref: str | None = None,
    status: str | None = None,
    actor_ref: str | None = None,
) -> dict:
    task = await run_agent_sync(
        create_task_for_agent,
        actor_ref=resolve_actor_ref(actor_ref),
        workspace_ref=workspace_ref,
        project_ref=project_ref,
        title=title,
        description=description,
        priority=priority,
        due_date=due_date,
        assignee_ref=assignee_ref,
        status=status,
    )
    return {
        "workspace": task.project.workspace.slug,
        "project": task.project.slug,
        "task": task.slug,
        "title": task.title,
        "status": task.status,
        "priority": task.priority,
        "assignee": task.assignee.username if task.assignee else None,
    }


@server.tool(
    name="ttm_update_task",
    description=(
        "Update an existing task by slug or title. Use assignee_ref='' to "
        "clear the assignee."
    ),
)
async def ttm_update_task(
    workspace_ref: str,
    project_ref: str,
    task_ref: str,
    title: str | None = None,
    description: str | None = None,
    priority: str | None = None,
    due_date: str | None = None,
    assignee_ref: str | None = None,
    status: str | None = None,
    actor_ref: str | None = None,
) -> dict:
    task = await run_agent_sync(
        update_task_for_agent,
        actor_ref=resolve_actor_ref(actor_ref),
        workspace_ref=workspace_ref,
        project_ref=project_ref,
        task_ref=task_ref,
        title=title,
        description=description,
        priority=priority,
        due_date=due_date,
        assignee_ref=assignee_ref,
        status=status,
    )
    return {
        "workspace": task.project.workspace.slug,
        "project": task.project.slug,
        "task": task.slug,
        "title": task.title,
        "status": task.status,
        "priority": task.priority,
        "assignee": task.assignee.username if task.assignee else None,
    }


@server.tool(
    name="ttm_close_task",
    description="Mark a task as done.",
)
async def ttm_close_task(
    workspace_ref: str,
    project_ref: str,
    task_ref: str,
    actor_ref: str | None = None,
) -> dict:
    task = await run_agent_sync(
        close_task_for_agent,
        actor_ref=resolve_actor_ref(actor_ref),
        workspace_ref=workspace_ref,
        project_ref=project_ref,
        task_ref=task_ref,
    )
    return {
        "workspace": task.project.workspace.slug,
        "project": task.project.slug,
        "task": task.slug,
        "title": task.title,
        "status": task.status,
    }


@server.tool(
    name="ttm_apply_request",
    description=(
        "Apply a structured, batch, markdown, or bilingual request directly "
        "through the TTM agent layer."
    ),
)
async def ttm_apply_request(
    request_text: str,
    preview: bool = False,
    actor_ref: str | None = None,
) -> list[dict]:
    return await run_agent_sync(
        execute_agent_batch_request,
        actor_ref=resolve_actor_ref(actor_ref),
        request_text=request_text,
        preview=preview,
    )


@server.tool(
    name="ttm_apply_file",
    description="Apply a local brief file through the TTM agent layer.",
)
async def ttm_apply_file(
    file_path: str,
    preview: bool = False,
    actor_ref: str | None = None,
) -> list[dict]:
    return await run_agent_sync(
        execute_agent_file_request,
        actor_ref=resolve_actor_ref(actor_ref),
        file_path=file_path,
        preview=preview,
    )


if __name__ == "__main__":
    server.run()
