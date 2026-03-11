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


def can_create_project(*, workspace, user) -> bool:
    return can_manage_workspace(workspace=workspace, user=user)


def can_view_project(*, project, user) -> bool:
    return can_view_workspace(workspace=project.workspace, user=user)


def can_create_task(*, project, user) -> bool:
    return can_view_project(project=project, user=user)


def can_view_task(*, task, user) -> bool:
    return can_view_project(project=task.project, user=user)


def can_assign_task(*, task, user) -> bool:
    return can_manage_workspace(workspace=task.project.workspace, user=user)


def can_change_task_status(*, task, user) -> bool:
    if can_manage_workspace(workspace=task.project.workspace, user=user):
        return True

    return getattr(task.assignee, "id", None) == getattr(user, "id", None)


def can_create_comment(*, task, user) -> bool:
    return can_view_task(task=task, user=user)


def can_delete_comment(*, comment, user) -> bool:
    if can_manage_workspace(workspace=comment.task.project.workspace, user=user):
        return True

    return getattr(comment.author, "id", None) == getattr(user, "id", None)
