from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from comments.models import Comment
from comments.services import add_comment
from core.logging_utils import context_extra, get_ttm_logger
from projects.models import Project
from projects.services import archive_project, create_project
from tasks.models import Task, TaskPriority, TaskStatus
from tasks.services import create_task, update_task
from workspaces.models import Invitation, Membership, MembershipRole, Workspace
from workspaces.services import create_invitation, create_workspace, delete_workspace

logger = get_ttm_logger("seed")
User = get_user_model()

DEFAULT_DEMO_PASSWORD = "demo12345"
DEMO_USER_SPECS = (
    ("demo_ui", "demo_ui@example.com"),
    ("ops_admin", "ops_admin@example.com"),
    ("teammate", "teammate@example.com"),
)
DEMO_WORKSPACE_SLUG = "north-star-studio"


def seed_demo_data(*, password: str = DEFAULT_DEMO_PASSWORD, reset: bool = False) -> dict:
    summary = {
        "users": 0,
        "workspace": 0,
        "memberships": 0,
        "projects": 0,
        "tasks": 0,
        "comments": 0,
        "invitations": 0,
        "reset": 0,
    }
    if reset:
        reset_demo_data(summary=summary)
    users = ensure_demo_users(password=password, summary=summary)
    workspace = ensure_demo_workspace(users=users, summary=summary)
    ensure_demo_memberships(workspace=workspace, users=users, summary=summary)
    ensure_demo_projects(workspace=workspace, users=users, summary=summary)
    ensure_demo_invitation(workspace=workspace, invited_by=users["demo_ui"], summary=summary)
    logger.info(
        "seed_demo_data_completed",
        extra=context_extra(
            workspace=workspace.slug,
            user=users["demo_ui"].username,
            action="seed_demo_data",
        ),
    )
    return {
        **summary,
        "workspace_slug": workspace.slug,
        "users_list": sorted(users),
        "password": password,
    }


def reset_demo_data(*, summary: dict) -> None:
    workspace = Workspace.objects.filter(slug=DEMO_WORKSPACE_SLUG).select_related("owner").first()
    if workspace is not None:
        delete_workspace(workspace=workspace, actor=workspace.owner)

    usernames = [username for username, _ in DEMO_USER_SPECS]
    User.objects.filter(username__in=usernames).delete()
    summary["reset"] = 1


def ensure_demo_users(*, password: str, summary: dict) -> dict[str, User]:
    users: dict[str, User] = {}
    for username, email in DEMO_USER_SPECS:
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": email},
        )
        if user.email != email:
            user.email = email
        user.set_password(password)
        user.save(update_fields=["email", "password"])
        if created:
            summary["users"] += 1
        users[username] = user
    return users


def ensure_demo_workspace(*, users: dict[str, User], summary: dict) -> Workspace:
    workspace = Workspace.objects.filter(slug=DEMO_WORKSPACE_SLUG).first()
    if workspace is None:
        workspace = create_workspace(owner=users["demo_ui"], name="North Star Studio")
        summary["workspace"] += 1
    return workspace


def ensure_demo_memberships(*, workspace: Workspace, users: dict[str, User], summary: dict) -> None:
    membership_specs = (
        ("demo_ui", MembershipRole.OWNER),
        ("ops_admin", MembershipRole.ADMIN),
        ("teammate", MembershipRole.MEMBER),
    )
    for username, role in membership_specs:
        membership, created = Membership.objects.get_or_create(
            workspace=workspace,
            user=users[username],
            defaults={"role": role},
        )
        if membership.role != role:
            membership.role = role
            membership.save(update_fields=["role"])
        if created:
            summary["memberships"] += 1

    Membership.objects.filter(
        workspace=workspace,
        role=MembershipRole.OWNER,
    ).exclude(user=users["demo_ui"]).update(role=MembershipRole.ADMIN)

    if workspace.owner_id != users["demo_ui"].id:
        workspace.owner = users["demo_ui"]
        workspace.save(update_fields=["owner", "updated_at"])


def ensure_demo_projects(*, workspace: Workspace, users: dict[str, User], summary: dict) -> None:
    launch_project = ensure_project(
        workspace=workspace,
        name="Launch Website Refresh",
        description="Marketing site cleanup, content polish, and analytics alignment.",
        actor=users["demo_ui"],
        summary=summary,
    )
    agent_project = ensure_project(
        workspace=workspace,
        name="Agent Intake",
        description="Operational automation and Codex-first workflow hardening.",
        actor=users["demo_ui"],
        summary=summary,
    )
    ops_project = ensure_project(
        workspace=workspace,
        name="Ops Cleanup Sprint",
        description="Archived project used to validate read-only operational behavior.",
        actor=users["demo_ui"],
        summary=summary,
    )

    today = timezone.localdate()
    launch_tasks = (
        {
            "title": "Finalize launch checklist",
            "description": "Close remaining launch blockers and confirm release readiness.",
            "priority": TaskPriority.HIGH,
            "assignee": users["teammate"],
            "status": TaskStatus.IN_PROGRESS,
            "due_date": today,
        },
        {
            "title": "Prepare analytics QA",
            "description": "Verify event names, dashboards, and conversion funnels.",
            "priority": TaskPriority.MEDIUM,
            "assignee": users["teammate"],
            "status": TaskStatus.TODO,
            "due_date": today + timedelta(days=2),
        },
        {
            "title": "Archive outdated landing assets",
            "description": "Remove stale media and archive previous launch artifacts.",
            "priority": TaskPriority.LOW,
            "assignee": users["ops_admin"],
            "status": TaskStatus.DONE,
            "due_date": today - timedelta(days=1),
        },
    )
    agent_tasks = (
        {
            "title": "Add MCP bootstrap notes",
            "description": "Document the local MCP bootstrap flow for Codex.",
            "priority": TaskPriority.HIGH,
            "assignee": users["ops_admin"],
            "status": TaskStatus.DONE,
            "due_date": today - timedelta(days=2),
        },
        {
            "title": "Add structured request examples",
            "description": "Show high-signal agent request examples for demo scenarios.",
            "priority": TaskPriority.MEDIUM,
            "assignee": users["teammate"],
            "status": TaskStatus.DONE,
            "due_date": today - timedelta(days=1),
        },
        {
            "title": "Publish plugin smoke tests",
            "description": "Validate plugin-driven list/create/update workflows end to end.",
            "priority": TaskPriority.HIGH,
            "assignee": users["teammate"],
            "status": TaskStatus.TODO,
            "due_date": today + timedelta(days=3),
        },
    )
    ops_tasks = (
        {
            "title": "Document archived cleanup outcomes",
            "description": "Preserve a closed sprint task in an archived project.",
            "priority": TaskPriority.MEDIUM,
            "assignee": users["ops_admin"],
            "status": TaskStatus.DONE,
            "due_date": today - timedelta(days=5),
        },
    )

    created_launch_tasks = ensure_tasks(
        project=launch_project,
        task_specs=launch_tasks,
        actor=users["demo_ui"],
        summary=summary,
    )
    ensure_tasks(
        project=agent_project,
        task_specs=agent_tasks,
        actor=users["demo_ui"],
        summary=summary,
    )
    ensure_tasks(
        project=ops_project,
        task_specs=ops_tasks,
        actor=users["demo_ui"],
        summary=summary,
    )

    if created_launch_tasks:
        first_task = created_launch_tasks[0]
    else:
        first_task = Task.objects.get(project=launch_project, slug="finalize-launch-checklist")

    ensure_comment(
        task=first_task,
        author=users["teammate"],
        text="Analytics QA is blocked on the final tag review.",
        summary=summary,
    )
    ensure_comment(
        task=first_task,
        author=users["demo_ui"],
        text="Release checklist updated after stakeholder sign-off.",
        summary=summary,
    )

    if not ops_project.is_archived:
        archive_project(project=ops_project, actor=users["demo_ui"])


def ensure_project(
    *,
    workspace: Workspace,
    name: str,
    description: str,
    actor,
    summary: dict,
) -> Project:
    project = Project.objects.filter(workspace=workspace, name=name).first()
    if project is None:
        project = create_project(
            workspace=workspace,
            name=name,
            description=description,
            created_by=actor,
        )
        summary["projects"] += 1
    elif project.description != description:
        project.description = description
        project.save(update_fields=["description", "updated_at"])
    return project


def ensure_tasks(
    *,
    project: Project,
    task_specs: tuple[dict, ...],
    actor,
    summary: dict,
) -> list[Task]:
    tasks: list[Task] = []
    for spec in task_specs:
        task = Task.objects.filter(project=project, title=spec["title"]).first()
        if task is None:
            if project.is_archived:
                raise ValueError(
                    "Archived seed project "
                    f"{project.slug} is missing task {spec['title']!r}."
                )
            task = create_task(
                project=project,
                title=spec["title"],
                description=spec["description"],
                priority=spec["priority"],
                due_date=spec["due_date"],
                assignee=spec["assignee"],
                created_by=actor,
            )
            task = update_task(
                task=task,
                actor=actor,
                status=spec["status"],
            )
            summary["tasks"] += 1
        elif not project.is_archived:
            task = update_task(
                task=task,
                actor=actor,
                description=spec["description"],
                priority=spec["priority"],
                due_date=spec["due_date"],
                assignee=spec["assignee"],
                status=spec["status"],
            )
        tasks.append(task)
    return tasks


def ensure_comment(*, task: Task, author, text: str, summary: dict) -> Comment:
    comment = Comment.objects.filter(task=task, author=author, text=text, is_deleted=False).first()
    if comment is None:
        comment = add_comment(task=task, author=author, text=text)
        summary["comments"] += 1
    return comment


def ensure_demo_invitation(*, workspace: Workspace, invited_by, summary: dict) -> Invitation:
    invitation = Invitation.objects.filter(
        workspace=workspace,
        email="newhire@example.com",
        accepted_at__isnull=True,
    ).first()
    if invitation is None:
        invitation = create_invitation(
            workspace=workspace,
            email="newhire@example.com",
            role=MembershipRole.MEMBER,
            invited_by=invited_by,
        )
        summary["invitations"] += 1
    return invitation
