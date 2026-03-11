from activity.models import ActivityLog


def log_activity(*, workspace, actor, action: str, target_type: str, target_id, metadata: dict | None = None) -> ActivityLog:
    return ActivityLog.objects.create(
        workspace=workspace,
        actor=actor,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        metadata=metadata or {},
    )
