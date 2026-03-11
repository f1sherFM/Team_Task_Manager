from django.db.models import QuerySet

from activity.models import ActivityLog
from workspaces.models import Workspace


def get_workspace_activity(workspace: Workspace) -> QuerySet[ActivityLog]:
    return (
        ActivityLog.objects.filter(workspace=workspace)
        .select_related("workspace", "actor")
        .order_by("-created_at")
    )
