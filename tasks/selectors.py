from django.contrib.auth import get_user_model
from django.db.models import QuerySet

from tasks.models import Task
from projects.models import Project


User = get_user_model()


def get_user_tasks(user) -> QuerySet[Task]:
    return (
        Task.objects.filter(project__workspace__memberships__user=user)
        .select_related("project", "project__workspace", "created_by", "assignee")
        .distinct()
    )


def get_project_tasks(*, project: Project) -> QuerySet[Task]:
    return (
        Task.objects.filter(project=project)
        .select_related("project", "project__workspace", "created_by", "assignee")
    )


def get_project_task_by_slug(
    *,
    workspace_slug: str,
    project_slug: str,
    task_slug: str,
    user,
) -> Task:
    return get_user_tasks(user).get(
        project__workspace__slug=workspace_slug,
        project__slug=project_slug,
        slug=task_slug,
    )


def get_project_task_candidates(*, project: Project) -> QuerySet[User]:
    return User.objects.filter(workspace_memberships__workspace=project.workspace).order_by("username").distinct()
