from django.db.models import QuerySet

from projects.models import Project
from workspaces.models import Workspace


def get_workspace_projects(*, workspace: Workspace) -> QuerySet[Project]:
    return Project.objects.filter(workspace=workspace).select_related("workspace", "created_by")


def get_project_by_slug(*, slug: str, user) -> Project:
    return (
        Project.objects.filter(workspace__memberships__user=user)
        .select_related("workspace", "created_by", "workspace__owner")
        .distinct()
        .get(slug=slug)
    )
