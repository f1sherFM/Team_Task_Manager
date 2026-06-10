from comments.models import Comment
from tasks.models import Task
from workspaces.models import Invitation, Membership, MembershipRole, Workspace


def run_integrity_checks() -> list[str]:
    issues: list[str] = []
    issues.extend(check_workspace_ownership_integrity())
    issues.extend(check_invitation_integrity())
    issues.extend(check_task_assignment_integrity())
    issues.extend(check_deleted_comment_integrity())
    return issues


def check_workspace_ownership_integrity() -> list[str]:
    issues: list[str] = []
    for workspace in Workspace.objects.select_related("owner").all():
        owner_memberships = list(
            Membership.objects.filter(
                workspace=workspace,
                role=MembershipRole.OWNER,
            ).select_related("user")
        )
        if len(owner_memberships) != 1:
            issues.append(
                f"Workspace {workspace.slug} has {len(owner_memberships)} owner memberships."
            )
            continue

        owner_membership = owner_memberships[0]
        if owner_membership.user_id != workspace.owner_id:
            issues.append(
                "Workspace "
                f"{workspace.slug} owner mismatch: workspace.owner={workspace.owner.username} "
                f"membership.user={owner_membership.user.username}."
            )
    return issues


def check_invitation_integrity() -> list[str]:
    issues: list[str] = []
    pending_invitations = Invitation.objects.filter(accepted_at__isnull=True).select_related(
        "workspace"
    )
    for invitation in pending_invitations:
        if Membership.objects.filter(
            workspace=invitation.workspace,
            user__email__iexact=invitation.email,
        ).exists():
            issues.append(
                "Pending invitation for "
                f"{invitation.email} in workspace {invitation.workspace.slug} "
                "targets an existing member."
            )

    accepted_invitations = Invitation.objects.filter(accepted_at__isnull=False).select_related(
        "workspace"
    )
    for invitation in accepted_invitations:
        if not Membership.objects.filter(
            workspace=invitation.workspace,
            user__email__iexact=invitation.email,
        ).exists():
            issues.append(
                "Accepted invitation for "
                f"{invitation.email} in workspace {invitation.workspace.slug} "
                "has no matching membership."
            )
    return issues


def check_task_assignment_integrity() -> list[str]:
    issues: list[str] = []
    tasks = Task.objects.select_related(
        "project__workspace",
        "assignee",
    ).exclude(assignee__isnull=True)
    for task in tasks:
        if not Membership.objects.filter(
            workspace=task.project.workspace,
            user=task.assignee,
        ).exists():
            issues.append(
                f"Task {task.slug} in project {task.project.slug} "
                f"is assigned to non-member {task.assignee.username}."
            )
    return issues


def check_deleted_comment_integrity() -> list[str]:
    issues: list[str] = []
    for comment in Comment.objects.filter(is_deleted=True).exclude(text=""):
        issues.append(f"Deleted comment {comment.id} still has stored text.")
    return issues
