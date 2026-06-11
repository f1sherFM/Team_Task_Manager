from django.contrib.auth import get_user_model
from django.db.models import Q, QuerySet
from django.utils import timezone

from core.selectors import parse_bool_query, parse_date_query
from projects.models import Project
from tasks.models import Task

User = get_user_model()


def get_user_tasks(user) -> QuerySet[Task]:
    return (
        Task.objects.filter(project__workspace__memberships__user=user)
        .select_related("project", "project__workspace", "created_by", "assignee")
        .distinct()
    )


def get_project_tasks(*, project: Project) -> QuerySet[Task]:
    return (
        Task.objects.filter(project=project)
        .select_related("project", "project__workspace", "created_by", "assignee")
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
        queryset = queryset.filter(assignee_id=assignee_id)
    if created_by_id:
        queryset = queryset.filter(created_by_id=created_by_id)

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
