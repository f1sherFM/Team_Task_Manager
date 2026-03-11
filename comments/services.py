from django.db import transaction

from activity.services import log_activity
from comments.models import Comment
from core.exceptions import DomainError
from core.permissions import can_create_comment, can_delete_comment
from tasks.models import Task


@transaction.atomic
def add_comment(*, task: Task, author, text: str) -> Comment:
    if not can_create_comment(task=task, user=author):
        raise DomainError("Only workspace members can comment on tasks.")

    comment = Comment.objects.create(task=task, author=author, text=text)
    log_activity(
        workspace=task.project.workspace,
        actor=author,
        action="comment_added",
        target_type="comment",
        target_id=comment.id,
        metadata={"task_id": task.id},
    )
    return comment


@transaction.atomic
def soft_delete_comment(*, comment: Comment, actor) -> Comment:
    if not can_delete_comment(comment=comment, user=actor):
        raise DomainError("Comment deletion requires author or admin access.")

    comment.is_deleted = True
    comment.text = ""
    comment.save(update_fields=["is_deleted", "text", "updated_at"])
    return comment
