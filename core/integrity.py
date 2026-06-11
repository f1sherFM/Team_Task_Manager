from comments.models import Comment
from projects.models import Project
from tasks.models import Task
from workspaces.models import Invitation, Membership, MembershipRole, Workspace


def run_integrity_checks() -> list[str]:
    issues: list[str] = []
    issues.extend(check_workspace_ownership_integrity())
    issues.extend(check_invitation_integrity())
    issues.extend(check_project_creator_integrity())
    issues.extend(check_task_creator_integrity())
    issues.extend(check_task_assignment_integrity())
    issues.extend(check_comment_author_integrity())
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
    for invitation in Invitation.objects.filter(role=MembershipRole.OWNER).select_related(
        "workspace"
    ):
        issues.append(
            "Invitation "
            f"{invitation.id} in workspace {invitation.workspace.slug} "
            "illegally grants the owner role."
        )

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
        if invitation.accepted_at and invitation.accepted_at > invitation.expires_at:
            issues.append(
                "Accepted invitation for "
                f"{invitation.email} in workspace {invitation.workspace.slug} "
                "was accepted after it expired."
            )
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


def check_project_creator_integrity() -> list[str]:
    issues: list[str] = []
    for project in Project.objects.select_related("workspace", "created_by"):
        if not Membership.objects.filter(
            workspace=project.workspace,
            user=project.created_by,
        ).exists():
            issues.append(
                f"Project {project.slug} in workspace {project.workspace.slug} "
                f"was created by non-member {project.created_by.username}."
            )
    return issues


def check_task_creator_integrity() -> list[str]:
    issues: list[str] = []
    tasks = Task.objects.select_related("project__workspace", "created_by")
    for task in tasks:
        if not Membership.objects.filter(
            workspace=task.project.workspace,
            user=task.created_by,
        ).exists():
            issues.append(
                f"Task {task.slug} in project {task.project.slug} "
                f"was created by non-member {task.created_by.username}."
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


def check_comment_author_integrity() -> list[str]:
    issues: list[str] = []
    comments = Comment.objects.select_related("task__project__workspace", "author")
    for comment in comments:
        if not Membership.objects.filter(
            workspace=comment.task.project.workspace,
            user=comment.author,
        ).exists():
            issues.append(
                f"Comment {comment.id} on task {comment.task.slug} "
                f"was authored by non-member {comment.author.username}."
            )
    return issues


def check_deleted_comment_integrity() -> list[str]:
    issues: list[str] = []
    for comment in Comment.objects.filter(is_deleted=True).exclude(text=""):
        issues.append(f"Deleted comment {comment.id} still has stored text.")
    return issues
