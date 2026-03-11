from django.db import transaction

from core.exceptions import DomainError
from core.permissions import can_assign_task, can_change_task_status, can_create_task
from core.slugs import generate_unique_slug
from tasks.models import Task
from projects.models import Project


@transaction.atomic
def create_task(
    *,
    project: Project,
    title: str,
    description: str,
    priority: str,
    due_date,
    assignee,
    created_by,
) -> Task:
    if not can_create_task(project=project, user=created_by):
        raise DomainError("Task creation requires workspace membership.")

    if assignee and not can_assign_task(task=_build_task_stub(project=project), user=created_by):
        raise DomainError("Only workspace admins can assign tasks.")

    if assignee and not project.workspace.memberships.filter(user=assignee).exists():
        raise DomainError("Assignee must be a workspace member.")

    slug = generate_unique_slug(
        model=Task,
        value=title,
        scope={"project": project},
    )
    return Task.objects.create(
        project=project,
        title=title,
        slug=slug,
        description=description,
        priority=priority,
        created_by=created_by,
        assignee=assignee,
        due_date=due_date,
    )


@transaction.atomic
def assign_task(*, task: Task, assignee, actor) -> Task:
    if not can_assign_task(task=task, user=actor):
        raise DomainError("Only workspace admins can assign tasks.")

    if assignee and not task.project.workspace.memberships.filter(user=assignee).exists():
        raise DomainError("Assignee must be a workspace member.")

    task.assignee = assignee
    task.save(update_fields=["assignee", "updated_at"])
    return task


@transaction.atomic
def change_task_status(*, task: Task, status: str, actor) -> Task:
    if not can_change_task_status(task=task, user=actor):
        raise DomainError("Status change requires admin access or assignee role.")

    task.status = status
    task.save(update_fields=["status", "updated_at"])
    return task


def _build_task_stub(*, project: Project) -> Task:
    return Task(project=project)
