from django.db.models import Case, CharField, F, QuerySet, Value, When

from comments.models import Comment
from tasks.models import Task


def get_user_comments(user) -> QuerySet[Comment]:
    return (
        Comment.objects.filter(task__project__workspace__memberships__user=user)
        .select_related("author", "task", "task__project", "task__project__workspace")
        .distinct()
        .annotate(
            display_text=Case(
                When(is_deleted=True, then=Value("[deleted]")),
                default=F("text"),
                output_field=CharField(),
            )
        )
    )


def get_task_comments(*, task: Task) -> QuerySet[Comment]:
    return (
        Comment.objects.filter(task=task)
        .select_related("author", "task", "task__project", "task__project__workspace")
        .annotate(
            display_text=Case(
                When(is_deleted=True, then=Value("[deleted]")),
                default=F("text"),
                output_field=CharField(),
            )
        )
    )


def get_comment_by_id(*, comment_id: int, user) -> Comment:
    return get_user_comments(user).get(id=comment_id)
