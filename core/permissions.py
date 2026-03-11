from django.contrib.auth.models import AnonymousUser


def is_authenticated(user) -> bool:
    return bool(user and not isinstance(user, AnonymousUser) and user.is_authenticated)


def has_membership_role(membership, *roles: str) -> bool:
    return bool(membership and membership.role in roles)


def get_workspace_membership(*, workspace, user):
    if not is_authenticated(user):
        return None

    from workspaces.models import Membership

    return Membership.objects.filter(workspace=workspace, user=user).first()


def can_view_workspace(*, workspace, user) -> bool:
    return get_workspace_membership(workspace=workspace, user=user) is not None


def can_manage_workspace(*, workspace, user) -> bool:
    from workspaces.models import MembershipRole

    membership = get_workspace_membership(workspace=workspace, user=user)
    return has_membership_role(membership, MembershipRole.OWNER, MembershipRole.ADMIN)
