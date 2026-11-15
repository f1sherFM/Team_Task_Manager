from django.db import transaction

from activity.services import log_activity
from core.exceptions import DomainError
from core.permissions import (
    can_archive_task,
    can_assign_task,
    can_change_task_status,
    can_create_task,
    can_delete_task,
    can_manage_tags,
    can_restore_task,
    can_update_task,
)
from core.slugs import create_with_unique_slug
from projects.models import Project
from tasks.models import Task, TaskChecklistItem, TaskTag
from tasks.validators import validate_hex_color
from workspaces.models import Workspace

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
    tags: list[TaskTag] | None = None,
) -> Task:
    if project.is_archived:
        raise DomainError("Tasks cannot be changed in archived projects.")

    if not can_create_task(project=project, user=created_by):
        raise DomainError("Task creation requires workspace membership.")

    if assignee and not can_assign_task(task=_build_task_stub(project=project), user=created_by):
        raise DomainError("Only workspace admins can assign tasks.")

    if assignee and not project.workspace.memberships.filter(user=assignee).exists():
        raise DomainError("Assignee must be a workspace member.")

    if tags:
        for tag in tags:
            if tag.workspace_id != project.workspace_id:
                raise DomainError("Cannot assign a tag from a different workspace.")

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
    if tags:
        task.tags.set(tags)

    log_activity(
        workspace=project.workspace,
        actor=created_by,
        action="task_created",
        target_type="task",
        target_id=str(task.id),
        metadata={"project_id": project.id, "task_title": task.title},
    )
    return task


@transaction.atomic
def assign_task(*, task: Task, assignee, actor) -> Task:
    if task.project.is_archived:
        raise DomainError("Tasks cannot be changed in archived projects.")

    if getattr(task, "is_archived", False):
        raise DomainError("Archived tasks cannot be changed.")

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
        target_id=str(task.id),
        metadata={
            "previous_assignee_id": previous_assignee_id,
            "assignee_id": assignee.id if assignee else None,
        },
    )
    return task


@transaction.atomic
def change_task_status(*, task: Task, status: str, actor) -> Task:
    if task.project.is_archived:
        raise DomainError("Tasks cannot be changed in archived projects.")

    if getattr(task, "is_archived", False):
        raise DomainError("Archived tasks cannot be changed.")

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
        target_id=str(task.id),
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


@transaction.atomic
def bulk_update_tasks(
    *,
    tasks: list[Task],
    actor,
    title=UNSET,
    description=UNSET,
    priority=UNSET,
    due_date=UNSET,
    assignee=UNSET,
    status=UNSET,
) -> list[Task]:
    if not tasks:
        raise DomainError("At least one task is required for bulk update.")

    project_id = tasks[0].project_id
    if any(task.project_id != project_id for task in tasks):
        raise DomainError("Bulk task updates must target a single project.")

    updated_tasks: list[Task] = []
    for task in tasks:
        updated_tasks.append(
            update_task(
                task=task,
                actor=actor,
                title=title,
                description=description,
                priority=priority,
                due_date=due_date,
                assignee=assignee,
                status=status,
            )
        )
    return updated_tasks


def update_task_details(
    *,
    task: Task,
    actor,
    title=UNSET,
    description=UNSET,
    priority=UNSET,
    due_date=UNSET,
) -> Task:
    if task.project.is_archived:
        raise DomainError("Tasks cannot be changed in archived projects.")

    if getattr(task, "is_archived", False):
        raise DomainError("Archived tasks cannot be changed.")

    if not can_update_task(task=task, user=actor):
        raise DomainError("Task updates are not allowed.")

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


@transaction.atomic
def archive_task(*, task: Task, actor) -> Task:
    if task.project.is_archived:
        raise DomainError("Tasks cannot be changed in archived projects.")

    if not can_archive_task(task=task, user=actor):
        raise DomainError("Permission denied to archive this task.")

    if task.is_archived:
        return task

    task.is_archived = True
    task.save(update_fields=["is_archived", "updated_at"])
    log_activity(
        workspace=task.project.workspace,
        actor=actor,
        action="task_archived",
        target_type="task",
        target_id=str(task.id),
        metadata={"task_title": task.title, "project_id": task.project_id},
    )
    return task


@transaction.atomic
def restore_task(*, task: Task, actor) -> Task:
    if task.project.is_archived:
        raise DomainError("Tasks cannot be changed in archived projects.")

    if not can_restore_task(task=task, user=actor):
        raise DomainError("Permission denied to restore this task.")

    if not task.is_archived:
        return task

    task.is_archived = False
    task.save(update_fields=["is_archived", "updated_at"])
    log_activity(
        workspace=task.project.workspace,
        actor=actor,
        action="task_restored",
        target_type="task",
        target_id=str(task.id),
        metadata={"task_title": task.title, "project_id": task.project_id},
    )
    return task


@transaction.atomic
def delete_task(*, task: Task, actor) -> None:
    if task.project.is_archived:
        raise DomainError("Tasks cannot be changed in archived projects.")

    if not can_delete_task(task=task, user=actor):
        raise DomainError("Only task creator or workspace admin can delete tasks.")

    workspace = task.project.workspace
    task_id = str(task.id)
    metadata = {
        "task_title": task.title,
        "task_slug": task.slug,
        "project_id": task.project_id,
        "project_slug": task.project.slug,
        "comments_deleted": task.comments.count(),
        "checklist_items_deleted": task.checklist_items.count(),
    }
    log_activity(
        workspace=workspace,
        actor=actor,
        action="task_deleted",
        target_type="task",
        target_id=task_id,
        metadata=metadata,
    )
    task.delete()


# ---------------------------------------------------------------------------
# Task Tags (Catalog & Association)
# ---------------------------------------------------------------------------


@transaction.atomic
def create_task_tag(
    *,
    workspace: Workspace,
    name: str,
    color: str = "#6c757d",
    actor,
) -> TaskTag:
    if not can_manage_tags(workspace=workspace, user=actor):
        raise DomainError("Only workspace admins can manage tags.")

    clean_name = name.strip()
    if not clean_name:
        raise DomainError("Tag name cannot be empty.")

    clean_color = color.strip().lower()
    try:
        validate_hex_color(clean_color)
    except Exception as exc:
        raise DomainError(str(exc)) from exc

    if workspace.tags.filter(name__iexact=clean_name).exists():
        raise DomainError(f"Tag with name '{clean_name}' already exists in this workspace.")

    tag = create_with_unique_slug(
        model=TaskTag,
        value=clean_name,
        scope={"workspace": workspace},
        create_kwargs={
            "workspace": workspace,
            "name": clean_name,
            "color": clean_color,
        },
    )
    log_activity(
        workspace=workspace,
        actor=actor,
        action="tag_created",
        target_type="workspace",
        target_id=str(workspace.id),
        metadata={"tag_id": tag.id, "tag_name": tag.name, "tag_color": tag.color},
    )
    return tag


@transaction.atomic
def update_task_tag(
    *,
    tag: TaskTag,
    actor,
    name: str = UNSET,
    color: str = UNSET,
) -> TaskTag:
    if not can_manage_tags(workspace=tag.workspace, user=actor):
        raise DomainError("Only workspace admins can manage tags.")

    update_fields = []
    if name is not UNSET:
        clean_name = name.strip()
        if not clean_name:
            raise DomainError("Tag name cannot be empty.")
        if tag.workspace.tags.filter(name__iexact=clean_name).exclude(id=tag.id).exists():
            raise DomainError(f"Tag with name '{clean_name}' already exists in this workspace.")
        if tag.name != clean_name:
            tag.name = clean_name
            update_fields.append("name")

    if color is not UNSET:
        clean_color = color.strip().lower()
        try:
            validate_hex_color(clean_color)
        except Exception as exc:
            raise DomainError(str(exc)) from exc
        if tag.color != clean_color:
            tag.color = clean_color
            update_fields.append("color")

    if update_fields:
        tag.save(update_fields=update_fields)
        log_activity(
            workspace=tag.workspace,
            actor=actor,
            action="tag_updated",
            target_type="workspace",
            target_id=str(tag.workspace_id),
            metadata={"tag_id": tag.id, "tag_name": tag.name, "tag_color": tag.color},
        )
    return tag


@transaction.atomic
def delete_task_tag(*, tag: TaskTag, actor) -> None:
    if not can_manage_tags(workspace=tag.workspace, user=actor):
        raise DomainError("Only workspace admins can manage tags.")

    workspace = tag.workspace
    metadata = {"tag_id": tag.id, "tag_name": tag.name}
    log_activity(
        workspace=workspace,
        actor=actor,
        action="tag_deleted",
        target_type="workspace",
        target_id=str(workspace.id),
        metadata=metadata,
    )
    tag.delete()


@transaction.atomic
def assign_tag_to_task(*, task: Task, tag: TaskTag, actor) -> Task:
    if not can_update_task(task=task, user=actor):
        raise DomainError("Permission denied to update task.")

    if tag.workspace_id != task.project.workspace_id:
        raise DomainError("Cannot assign a tag from a different workspace.")

    task.tags.add(tag)
    log_activity(
        workspace=task.project.workspace,
        actor=actor,
        action="task_tags_updated",
        target_type="task",
        target_id=str(task.id),
        metadata={"action": "add", "tag_id": tag.id, "tag_name": tag.name},
    )
    return task


@transaction.atomic
def remove_tag_from_task(*, task: Task, tag: TaskTag, actor) -> Task:
    if not can_update_task(task=task, user=actor):
        raise DomainError("Permission denied to update task.")

    task.tags.remove(tag)
    log_activity(
        workspace=task.project.workspace,
        actor=actor,
        action="task_tags_updated",
        target_type="task",
        target_id=str(task.id),
        metadata={"action": "remove", "tag_id": tag.id, "tag_name": tag.name},
    )
    return task


@transaction.atomic
def set_task_tags(*, task: Task, tags: list[TaskTag], actor) -> Task:
    if not can_update_task(task=task, user=actor):
        raise DomainError("Permission denied to update task.")

    for tag in tags:
        if tag.workspace_id != task.project.workspace_id:
            raise DomainError("Cannot assign a tag from a different workspace.")

    task.tags.set(tags)
    log_activity(
        workspace=task.project.workspace,
        actor=actor,
        action="task_tags_updated",
        target_type="task",
        target_id=str(task.id),
        metadata={"tag_ids": [t.id for t in tags], "tag_names": [t.name for t in tags]},
    )
    return task


# ---------------------------------------------------------------------------
# Task Checklists
# ---------------------------------------------------------------------------


@transaction.atomic
def add_checklist_item(
    *,
    task: Task,
    text: str,
    actor,
    position: int | None = None,
) -> TaskChecklistItem:
    if not can_update_task(task=task, user=actor):
        raise DomainError("Permission denied to update task checklist.")

    clean_text = text.strip()
    if not clean_text:
        raise DomainError("Checklist item text cannot be empty.")

    if position is None:
        position = task.checklist_items.count()

    item = TaskChecklistItem.objects.create(
        task=task,
        text=clean_text,
        position=position,
    )
    log_activity(
        workspace=task.project.workspace,
        actor=actor,
        action="checklist_item_added",
        target_type="task",
        target_id=str(task.id),
        metadata={"item_id": item.id, "text": item.text, "position": item.position},
    )
    return item


@transaction.atomic
def update_checklist_item(
    *,
    item: TaskChecklistItem,
    actor,
    text: str = UNSET,
    is_completed: bool = UNSET,
) -> TaskChecklistItem:
    if not can_update_task(task=item.task, user=actor):
        raise DomainError("Permission denied to update task checklist.")

    update_fields = []
    if text is not UNSET:
        clean_text = text.strip()
        if not clean_text:
            raise DomainError("Checklist item text cannot be empty.")
        if item.text != clean_text:
            item.text = clean_text
            update_fields.append("text")

    if is_completed is not UNSET:
        val = bool(is_completed)
        if item.is_completed != val:
            item.is_completed = val
            update_fields.append("is_completed")

    if update_fields:
        item.save(update_fields=[*update_fields, "updated_at"])
        log_activity(
            workspace=item.task.project.workspace,
            actor=actor,
            action="checklist_item_updated",
            target_type="task",
            target_id=str(item.task_id),
            metadata={"item_id": item.id, "text": item.text, "is_completed": item.is_completed},
        )
    return item


@transaction.atomic
def toggle_checklist_item(*, item: TaskChecklistItem, actor) -> TaskChecklistItem:
    if not can_update_task(task=item.task, user=actor):
        raise DomainError("Permission denied to update task checklist.")

    item.is_completed = not item.is_completed
    item.save(update_fields=["is_completed", "updated_at"])
    log_activity(
        workspace=item.task.project.workspace,
        actor=actor,
        action="checklist_item_toggled",
        target_type="task",
        target_id=str(item.task_id),
        metadata={"item_id": item.id, "is_completed": item.is_completed},
    )
    return item


@transaction.atomic
def delete_checklist_item(*, item: TaskChecklistItem, actor) -> None:
    task = item.task
    if not can_update_task(task=task, user=actor):
        raise DomainError("Permission denied to update task checklist.")

    item_id = item.id
    item.delete()

    # Re-normalize positions so there are no gaps
    for pos, it in enumerate(task.checklist_items.order_by("position", "id")):
        if it.position != pos:
            it.position = pos
            it.save(update_fields=["position", "updated_at"])

    log_activity(
        workspace=task.project.workspace,
        actor=actor,
        action="checklist_item_deleted",
        target_type="task",
        target_id=str(task.id),
        metadata={"item_id": item_id},
    )


@transaction.atomic
def reorder_checklist_items(
    *,
    task: Task,
    item_ids: list[int],
    actor,
) -> list[TaskChecklistItem]:
    if not can_update_task(task=task, user=actor):
        raise DomainError("Permission denied to update task checklist.")

    current_items = list(task.checklist_items.all())
    current_ids = {it.id for it in current_items}
    if set(item_ids) != current_ids or len(item_ids) != len(current_items):
        raise DomainError("Invalid checklist item IDs provided for reordering.")

    items_map = {it.id: it for it in current_items}
    for pos, item_id in enumerate(item_ids):
        it = items_map[item_id]
        if it.position != pos:
            it.position = pos
            it.save(update_fields=["position", "updated_at"])

    log_activity(
        workspace=task.project.workspace,
        actor=actor,
        action="checklist_reordered",
        target_type="task",
        target_id=str(task.id),
        metadata={"ordered_item_ids": item_ids},
    )
    return list(task.checklist_items.order_by("position", "id"))


def _build_task_stub(*, project: Project) -> Task:
    return Task(project=project)
