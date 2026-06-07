from django.db.models import Count
from django.utils import timezone

from activity.models import ActivityLog
from projects.models import Project
from tasks.models import Task
from workspaces.models import Invitation, Workspace


def get_home_dashboard(*, user) -> dict:
    today = timezone.localdate()

    workspace_queryset = (
        Workspace.objects.filter(memberships__user=user)
        .select_related("owner")
        .annotate(
            project_count=Count("projects", distinct=True),
            member_count=Count("memberships", distinct=True),
        )
        .distinct()
        .order_by("name")
    )
    project_queryset = (
        Project.objects.filter(workspace__memberships__user=user)
        .select_related("workspace", "created_by")
        .distinct()
        .order_by("-created_at")
    )
    task_queryset = (
        Task.objects.filter(project__workspace__memberships__user=user)
        .select_related("project", "project__workspace", "assignee")
        .distinct()
        .order_by("due_date", "-created_at")
    )
    activity_queryset = (
        ActivityLog.objects.filter(workspace__memberships__user=user)
        .select_related("workspace", "actor")
        .distinct()
        .order_by("-created_at")
    )
    invitation_queryset = (
        Invitation.objects.filter(
            workspace__memberships__user=user,
            accepted_at__isnull=True,
        )
        .select_related("workspace", "invited_by")
        .distinct()
        .order_by("expires_at")
    )

    return {
        "workspace_count": workspace_queryset.count(),
        "project_count": project_queryset.count(),
        "active_project_count": project_queryset.filter(is_archived=False).count(),
        "archived_project_count": project_queryset.filter(is_archived=True).count(),
        "task_count": task_queryset.count(),
        "todo_task_count": task_queryset.filter(status="todo").count(),
        "in_progress_task_count": task_queryset.filter(status="in_progress").count(),
        "done_task_count": task_queryset.filter(status="done").count(),
        "overdue_task_count": task_queryset.filter(
            due_date__lt=today,
        ).exclude(status="done").count(),
        "due_soon_tasks": task_queryset.filter(
            due_date__isnull=False,
            due_date__gte=today,
        ).exclude(status="done")[:5],
        "recent_workspaces": workspace_queryset[:4],
        "recent_projects": project_queryset[:5],
        "recent_activity": activity_queryset[:6],
        "pending_invitations": invitation_queryset[:5],
    }
