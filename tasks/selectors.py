from django.contrib.auth import get_user_model
from django.db.models import Q, QuerySet
from django.utils import timezone

from core.selectors import parse_bool_query, parse_date_query
from projects.models import Project
from tasks.models import Task, TaskChecklistItem, TaskPriority, TaskStatus, TaskTag
from workspaces.models import Workspace

User = get_user_model()


def get_user_tasks(user) -> QuerySet[Task]:
    return (
        Task.objects.filter(project__workspace__memberships__user=user)
        .select_related("project", "project__workspace", "created_by", "assignee")
        .prefetch_related("tags__workspace", "checklist_items")
        .order_by("created_at", "id")
        .distinct()
    )


def get_project_tasks(*, project: Project) -> QuerySet[Task]:
    return (
        Task.objects.filter(project=project)
        .select_related("project", "project__workspace", "created_by", "assignee")
        .prefetch_related("tags__workspace", "checklist_items")
        .order_by("created_at", "id")
    )


def get_project_task_by_slug(
    *,
    workspace_slug: str,
    project_slug: str,
    task_slug: str,
    user,
) -> Task:
    return get_user_tasks(user).get(
        project__workspace__slug=workspace_slug,
        project__slug=project_slug,
        slug=task_slug,
    )


def get_project_task_candidates(*, project: Project) -> QuerySet[User]:
    return (
        User.objects.filter(workspace_memberships__workspace=project.workspace)
        .order_by("username")
        .distinct()
    )


def get_workspace_tags(*, workspace: Workspace) -> QuerySet[TaskTag]:
    return (
        TaskTag.objects.filter(workspace=workspace)
        .select_related("workspace")
        .order_by("name", "id")
    )


def get_workspace_tag_by_slug(*, workspace: Workspace, slug: str) -> TaskTag:
    return get_workspace_tags(workspace=workspace).get(slug=slug)


def get_workspace_tag_by_id(*, workspace: Workspace, tag_id: int) -> TaskTag:
    return get_workspace_tags(workspace=workspace).get(id=tag_id)


def get_task_checklist_items(*, task: Task) -> QuerySet[TaskChecklistItem]:
    return task.checklist_items.order_by("position", "id")


def get_task_checklist_item_by_id(*, task: Task, item_id: int) -> TaskChecklistItem:
    return task.checklist_items.get(id=item_id)


def filter_tasks(
    queryset: QuerySet[Task],
    *,
    workspace_slug: str | None = None,
    project_slug: str | None = None,
    status_value: str | None = None,
    priority: str | None = None,
    assignee_id: str | None = None,
    created_by_id: str | None = None,
    due_before: str | None = None,
    due_after: str | None = None,
    is_overdue: str | None = None,
    is_archived: bool | None = None,
    tag_slug: str | None = None,
    search: str | None = None,
) -> QuerySet[Task]:
    if workspace_slug:
        queryset = queryset.filter(project__workspace__slug=workspace_slug)
    if project_slug:
        queryset = queryset.filter(project__slug=project_slug)
    if status_value and status_value in TaskStatus.values:
        queryset = queryset.filter(status=status_value)
    if priority and priority in TaskPriority.values:
        queryset = queryset.filter(priority=priority)
    if assignee_id:
        if assignee_id in ("unassigned", "none"):
            queryset = queryset.filter(assignee__isnull=True)
        else:
            try:
                valid_assignee_id = int(assignee_id)
                if valid_assignee_id > 0:
                    queryset = queryset.filter(assignee_id=valid_assignee_id)
                else:
                    raise ValueError(f"Invalid integer value for assignee: {assignee_id}.")
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid integer value for assignee: {assignee_id}.") from exc
    if created_by_id:
        try:
            valid_creator_id = int(created_by_id)
            if valid_creator_id > 0:
                queryset = queryset.filter(created_by_id=valid_creator_id)
            else:
                raise ValueError(f"Invalid integer value for created_by: {created_by_id}.")
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid integer value for created_by: {created_by_id}.") from exc
    if is_archived is not None:
        queryset = queryset.filter(is_archived=is_archived)
    if tag_slug:
        cleaned_tag = tag_slug.strip()
        if cleaned_tag:
            queryset = queryset.filter(tags__slug=cleaned_tag)

    parsed_due_before = parse_date_query(due_before, param_name="due_before")
    if parsed_due_before is not None:
        queryset = queryset.filter(due_date__lte=parsed_due_before)

    parsed_due_after = parse_date_query(due_after, param_name="due_after")
    if parsed_due_after is not None:
        queryset = queryset.filter(due_date__gte=parsed_due_after)

    overdue_filter = parse_bool_query(is_overdue, param_name="is_overdue")
    if overdue_filter is True:
        queryset = queryset.filter(
            due_date__lt=timezone.localdate()
        ).exclude(status="done")
    elif overdue_filter is False:
        queryset = queryset.exclude(
            due_date__lt=timezone.localdate()
        ).exclude(status="done")

    if search:
        search_term = search.strip()
        if search_term:
            queryset = queryset.filter(
                Q(title__icontains=search_term)
                | Q(description__icontains=search_term)
                | Q(slug__icontains=search_term)
            )
    return queryset


def get_kanban_board_tasks(
    *,
    project: Project,
    per_column_limit: int = 20,
    status_value: str | None = None,
    priority: str | None = None,
    assignee_id: str | None = None,
    tag_slug: str | None = None,
    is_overdue: str | None = None,
    is_archived: bool | None = False,
    search: str | None = None,
) -> dict:
    base_qs = get_project_tasks(project=project)
    filtered_qs = filter_tasks(
        base_qs,
        priority=priority,
        assignee_id=assignee_id,
        tag_slug=tag_slug,
        is_overdue=is_overdue,
        is_archived=is_archived,
        search=search,
    )

    column_definitions = [
        ("todo", "To Do", "border-secondary"),
        ("in_progress", "In Progress", "border-primary"),
        ("done", "Done", "border-success"),
    ]

    board = {}
    for col_status, col_name, col_border in column_definitions:
        if status_value and status_value != col_status:
            board[col_status] = {
                "status": col_status,
                "name": col_name,
                "border_class": col_border,
                "total_count": 0,
                "tasks": [],
                "has_more": False,
                "next_cursor": None,
                "next_offset": None,
                "remaining_count": 0,
            }
            continue

        col_qs = filtered_qs.filter(status=col_status).order_by("-created_at", "-id")
        total_count = col_qs.count()
        slice_tasks = list(col_qs[: per_column_limit + 1])
        has_more = len(slice_tasks) > per_column_limit
        tasks = slice_tasks[:per_column_limit]
        next_cursor = (
            f"{tasks[-1].created_at.isoformat()}__{tasks[-1].id}"
            if has_more and tasks
            else None
        )
        next_offset = per_column_limit if has_more else None
        remaining_count = max(0, total_count - len(tasks))

        board[col_status] = {
            "status": col_status,
            "name": col_name,
            "border_class": col_border,
            "total_count": total_count,
            "tasks": tasks,
            "has_more": has_more,
            "next_cursor": next_cursor,
            "next_offset": next_offset,
            "remaining_count": remaining_count,
        }

    return board


def get_kanban_column_page(
    *,
    project: Project,
    status: str,
    cursor: str | None = None,
    offset: int = 0,
    limit: int = 20,
    priority: str | None = None,
    assignee_id: str | None = None,
    tag_slug: str | None = None,
    is_overdue: str | None = None,
    is_archived: bool | None = False,
    search: str | None = None,
) -> dict:
    from datetime import datetime

    base_qs = get_project_tasks(project=project)
    filtered_qs = filter_tasks(
        base_qs,
        priority=priority,
        assignee_id=assignee_id,
        tag_slug=tag_slug,
        is_overdue=is_overdue,
        is_archived=is_archived,
        search=search,
    )
    col_qs = filtered_qs.filter(status=status).order_by("-created_at", "-id")
    total_count = col_qs.count()

    if cursor:
        try:
            cursor_created_at_str, cursor_id_str = cursor.split("__", 1)
            cursor_created_at = datetime.fromisoformat(cursor_created_at_str)
            cursor_id = int(cursor_id_str)
            col_qs = col_qs.filter(
                Q(created_at__lt=cursor_created_at)
                | Q(created_at=cursor_created_at, id__lt=cursor_id)
            )
        except (ValueError, TypeError):
            if offset > 0:
                col_qs = col_qs[offset:]
    elif offset > 0:
        col_qs = col_qs[offset:]

    slice_tasks = list(col_qs[: limit + 1])
    has_more = len(slice_tasks) > limit
    tasks = slice_tasks[:limit]
    next_cursor = (
        f"{tasks[-1].created_at.isoformat()}__{tasks[-1].id}"
        if has_more and tasks
        else None
    )
    remaining_count = max(0, col_qs.count() - len(tasks))
    next_offset = (offset + len(tasks)) if has_more else None

    return {
        "status": status,
        "tasks": tasks,
        "total_count": total_count,
        "has_more": has_more,
        "next_cursor": next_cursor,
        "next_offset": next_offset,
        "remaining_count": remaining_count,
    }
