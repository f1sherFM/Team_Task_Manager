from django.db.models import QuerySet

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
