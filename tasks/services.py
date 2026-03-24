from django.db import transaction

from activity.services import log_activity
from core.exceptions import DomainError
from core.permissions import can_assign_task, can_change_task_status, can_create_task, can_view_task
from core.slugs import create_with_unique_slug
from tasks.models import Task
from projects.models import Project


UNSET = object()


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

    task = create_with_unique_slug(
        model=Task,
        value=title,
        scope={"project": project},
        create_kwargs={
            "project": project,
            "title": title,
            "description": description,
            "priority": priority,
            "created_by": created_by,
            "assignee": assignee,
            "due_date": due_date,
        },
    )
    log_activity(
        workspace=project.workspace,
        actor=created_by,
        action="task_created",
        target_type="task",
        target_id=task.id,
        metadata={"project_id": project.id, "task_title": task.title},
    )
    return task


@transaction.atomic
def assign_task(*, task: Task, assignee, actor) -> Task:
    if not can_assign_task(task=task, user=actor):
        raise DomainError("Only workspace admins can assign tasks.")

    if assignee and not task.project.workspace.memberships.filter(user=assignee).exists():
        raise DomainError("Assignee must be a workspace member.")

    previous_assignee_id = task.assignee_id
    task.assignee = assignee
    task.save(update_fields=["assignee", "updated_at"])
    log_activity(
        workspace=task.project.workspace,
        actor=actor,
        action="task_assigned",
        target_type="task",
        target_id=task.id,
        metadata={
            "previous_assignee_id": previous_assignee_id,
            "assignee_id": assignee.id if assignee else None,
        },
    )
    return task


@transaction.atomic
def change_task_status(*, task: Task, status: str, actor) -> Task:
    if not can_change_task_status(task=task, user=actor):
        raise DomainError("Status change requires admin access or assignee role.")

    previous_status = task.status
    task.status = status
    task.save(update_fields=["status", "updated_at"])
    log_activity(
        workspace=task.project.workspace,
        actor=actor,
        action="task_status_changed",
        target_type="task",
        target_id=task.id,
        metadata={"previous_status": previous_status, "status": status},
    )
    return task


@transaction.atomic
def update_task(
    *,
    task: Task,
    actor,
    title=UNSET,
    description=UNSET,
    priority=UNSET,
    due_date=UNSET,
    assignee=UNSET,
    status=UNSET,
) -> Task:
    task = update_task_details(
        task=task,
        actor=actor,
        title=title,
        description=description,
        priority=priority,
        due_date=due_date,
    )

    if assignee is not UNSET and assignee != task.assignee:
        task = assign_task(task=task, assignee=assignee, actor=actor)
    if status is not UNSET and status != task.status:
        task = change_task_status(task=task, status=status, actor=actor)
    return task


def update_task_details(
    *,
    task: Task,
    actor,
    title=UNSET,
    description=UNSET,
    priority=UNSET,
    due_date=UNSET,
) -> Task:
    if not can_view_task(task=task, user=actor):
        raise DomainError("Task update requires workspace membership.")

    update_fields = []
    for field_name, value in (
        ("title", title),
        ("description", description),
        ("priority", priority),
        ("due_date", due_date),
    ):
        if value is UNSET or getattr(task, field_name) == value:
            continue
        setattr(task, field_name, value)
        update_fields.append(field_name)

    if not update_fields:
        return task

    task.save(update_fields=[*update_fields, "updated_at"])
    return task


def _build_task_stub(*, project: Project) -> Task:
    return Task(project=project)
