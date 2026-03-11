from django.db.models import QuerySet

from workspaces.models import Membership, Workspace


def get_user_workspaces(user) -> QuerySet[Workspace]:
    return (
        Workspace.objects.filter(memberships__user=user)
        .select_related("owner")
        .distinct()
    )


def get_workspace_members(workspace: Workspace) -> QuerySet[Membership]:
    return Membership.objects.filter(workspace=workspace).select_related("user", "workspace")


def get_workspace_by_slug(slug: str) -> Workspace:
    return Workspace.objects.select_related("owner").get(slug=slug)
