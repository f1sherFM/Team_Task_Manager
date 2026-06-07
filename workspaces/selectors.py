from django.db.models import QuerySet

from workspaces.models import Invitation, Membership, Workspace


def get_user_workspaces(user) -> QuerySet[Workspace]:
    return (
        Workspace.objects.filter(memberships__user=user)
        .select_related("owner")
        .distinct()
    )


def get_workspace_members(workspace: Workspace) -> QuerySet[Membership]:
    return Membership.objects.filter(workspace=workspace).select_related("user", "workspace")


def get_workspace_invitations(workspace: Workspace) -> QuerySet[Invitation]:
    return (
        Invitation.objects.filter(workspace=workspace)
        .select_related("workspace", "invited_by")
        .order_by("-created_at")
    )


def get_workspace_by_slug(slug: str) -> Workspace:
    return Workspace.objects.select_related("owner").get(slug=slug)


def get_user_workspace_by_slug(*, slug: str, user) -> Workspace:
    return get_user_workspaces(user).get(slug=slug)


def get_invitation_by_token(*, token) -> Invitation:
    return Invitation.objects.select_related("workspace", "invited_by").get(token=token)


def get_workspace_membership_by_id(*, workspace: Workspace, membership_id: int) -> Membership:
    return Membership.objects.select_related("user", "workspace").get(
        workspace=workspace,
        id=membership_id,
    )


def get_workspace_invitation_by_id(*, workspace: Workspace, invitation_id: int) -> Invitation:
    return Invitation.objects.select_related("workspace", "invited_by").get(
        workspace=workspace,
        id=invitation_id,
    )
