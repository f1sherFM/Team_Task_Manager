from django.contrib.auth import get_user_model
from django.db.models import Q, QuerySet
from django.utils import timezone

from core.selectors import parse_bool_query, parse_date_query
from projects.models import Project
from tasks.models import Task, TaskChecklistItem, TaskTag
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
    if status_value:
        queryset = queryset.filter(status=status_value)
    if priority:
        queryset = queryset.filter(priority=priority)
    if assignee_id:
        if assignee_id in ("unassigned", "none"):
            queryset = queryset.filter(assignee__isnull=True)
        else:
            queryset = queryset.filter(assignee_id=assignee_id)
    if created_by_id:
        queryset = queryset.filter(created_by_id=created_by_id)
    if is_archived is not None:
        queryset = queryset.filter(is_archived=is_archived)
    if tag_slug:
        queryset = queryset.filter(tags__slug=tag_slug)

    parsed_due_before = parse_date_query(due_before, param_name="due_before")
    parsed_due_after = parse_date_query(due_after, param_name="due_after")
    if parsed_due_before is not None:
        queryset = queryset.filter(due_date__lte=parsed_due_before)
    if parsed_due_after is not None:
        queryset = queryset.filter(due_date__gte=parsed_due_after)

    overdue_filter = parse_bool_query(is_overdue, param_name="is_overdue")
    if overdue_filter is True:
        queryset = queryset.filter(due_date__lt=timezone.localdate()).exclude(status="done")
    elif overdue_filter is False:
        queryset = queryset.exclude(due_date__lt=timezone.localdate()).exclude(status="done")

    if search:
        queryset = queryset.filter(
            Q(title__icontains=search)
            | Q(description__icontains=search)
            | Q(slug__icontains=search)
        )
    return queryset
