from django.db.models import Q, QuerySet

from projects.models import Project
from workspaces.models import Workspace


def get_user_projects(user) -> QuerySet[Project]:
    return (
        Project.objects.filter(workspace__memberships__user=user)
        .select_related("workspace", "created_by", "workspace__owner")
        .distinct()
    )


def get_workspace_projects(*, workspace: Workspace) -> QuerySet[Project]:
    return (
        Project.objects.filter(workspace=workspace)
        .select_related("workspace", "created_by", "workspace__owner")
    )


def get_workspace_project_by_slug(*, workspace_slug: str, project_slug: str, user) -> Project:
    return get_user_projects(user).get(
        workspace__slug=workspace_slug,
        slug=project_slug,
    )


def filter_projects(
    queryset: QuerySet[Project],
    *,
    workspace_slug: str | None = None,
    created_by_id: str | None = None,
    is_archived: bool | None = None,
    search: str | None = None,
) -> QuerySet[Project]:
    if workspace_slug:
        queryset = queryset.filter(workspace__slug=workspace_slug)
    if created_by_id:
        queryset = queryset.filter(created_by_id=created_by_id)
    if is_archived is not None:
        queryset = queryset.filter(is_archived=is_archived)
    if search:
        queryset = queryset.filter(
            Q(name__icontains=search)
            | Q(description__icontains=search)
            | Q(slug__icontains=search)
        )
    return queryset
