from django.db.models import QuerySet

from activity.models import ActivityLog
from workspaces.models import Workspace


def get_user_activity(user) -> QuerySet[ActivityLog]:
    return (
        ActivityLog.objects.filter(workspace__memberships__user=user)
        .select_related("workspace", "actor")
        .distinct()
        .order_by("-created_at")
    )


def get_workspace_activity(workspace: Workspace) -> QuerySet[ActivityLog]:
    return (
        ActivityLog.objects.filter(workspace=workspace)
        .select_related("workspace", "actor")
        .order_by("-created_at")
    )


def filter_activity_logs(
    queryset: QuerySet[ActivityLog],
    *,
    workspace_slug: str | None = None,
    actor_id: str | None = None,
    action: str | None = None,
    target_type: str | None = None,
) -> QuerySet[ActivityLog]:
    if workspace_slug:
        queryset = queryset.filter(workspace__slug=workspace_slug)
    if actor_id:
        queryset = queryset.filter(actor_id=actor_id)
    if action:
        queryset = queryset.filter(action=action)
    if target_type:
        queryset = queryset.filter(target_type=target_type)
    return queryset
