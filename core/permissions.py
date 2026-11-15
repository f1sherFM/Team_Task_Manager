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


def can_manage_invitations(*, workspace, user) -> bool:
    return can_manage_workspace(workspace=workspace, user=user)


def can_transfer_workspace_ownership(*, workspace, user) -> bool:
    from workspaces.models import MembershipRole

    membership = get_workspace_membership(workspace=workspace, user=user)
    return has_membership_role(membership, MembershipRole.OWNER)


def can_delete_workspace(*, workspace, user) -> bool:
    return can_transfer_workspace_ownership(workspace=workspace, user=user)


def can_manage_membership(*, membership, user) -> bool:
    from workspaces.models import MembershipRole

    actor_membership = get_workspace_membership(workspace=membership.workspace, user=user)
    if actor_membership is None:
        return False
    if membership.role == MembershipRole.OWNER:
        return (
            actor_membership.role == MembershipRole.OWNER
            and actor_membership.user_id == membership.user_id
        )
    if actor_membership.role == MembershipRole.OWNER:
        return True
    if actor_membership.role == MembershipRole.ADMIN:
        return membership.role == MembershipRole.MEMBER
    return False


def can_view_project(*, project, user) -> bool:
    return can_view_workspace(workspace=project.workspace, user=user)


def can_archive_project(*, project, user) -> bool:
    return can_manage_workspace(workspace=project.workspace, user=user)


def is_project_writable(project) -> bool:
    return not project.is_archived


def is_task_writable(task) -> bool:
    return is_project_writable(task.project) and not getattr(task, "is_archived", False)


def can_create_task(*, project, user) -> bool:
    return can_view_project(project=project, user=user) and is_project_writable(project)


def can_view_task(*, task, user) -> bool:
    return can_view_project(project=task.project, user=user)


def can_update_task(*, task, user) -> bool:
    return can_view_task(task=task, user=user) and is_task_writable(task)


def can_assign_task(*, task, user) -> bool:
    return can_manage_workspace(workspace=task.project.workspace, user=user) and is_task_writable(
        task
    )


def can_change_task_status(*, task, user) -> bool:
    if not is_task_writable(task) or not can_view_task(task=task, user=user):
        return False

    if can_manage_workspace(workspace=task.project.workspace, user=user):
        return True

    user_id = getattr(user, "id", None)
    if user_id is None:
        return False

    assignee_id = getattr(task, "assignee_id", None)
    return assignee_id is not None and assignee_id == user_id


def can_delete_task(*, task, user) -> bool:
    if not is_project_writable(task.project) or not can_view_task(task=task, user=user):
        return False

    if can_manage_workspace(workspace=task.project.workspace, user=user):
        return True

    user_id = getattr(user, "id", None)
    if user_id is None:
        return False

    created_by_id = getattr(task, "created_by_id", None)
    return created_by_id is not None and created_by_id == user_id


def can_archive_task(*, task, user) -> bool:
    if not is_project_writable(task.project) or not can_view_task(task=task, user=user):
        return False

    if can_manage_workspace(workspace=task.project.workspace, user=user):
        return True

    user_id = getattr(user, "id", None)
    if user_id is None:
        return False

    created_by_id = getattr(task, "created_by_id", None)
    if created_by_id is not None and created_by_id == user_id:
        return True

    assignee_id = getattr(task, "assignee_id", None)
    return assignee_id is not None and assignee_id == user_id


def can_restore_task(*, task, user) -> bool:
    return can_archive_task(task=task, user=user)


def can_view_tags(*, workspace, user) -> bool:
    return can_view_workspace(workspace=workspace, user=user)


def can_manage_tags(*, workspace, user) -> bool:
    return can_manage_workspace(workspace=workspace, user=user)


def can_manage_checklist(*, task, user) -> bool:
    return can_update_task(task=task, user=user)


def can_create_comment(*, task, user) -> bool:
    return can_view_task(task=task, user=user) and is_task_writable(task)


def can_delete_comment(*, comment, user) -> bool:
    if not is_task_writable(comment.task) or not can_view_task(task=comment.task, user=user):
        return False

    if can_manage_workspace(workspace=comment.task.project.workspace, user=user):
        return True

    user_id = getattr(user, "id", None)
    if user_id is None:
        return False

    author_id = getattr(comment, "author_id", None)
    return author_id is not None and author_id == user_id
