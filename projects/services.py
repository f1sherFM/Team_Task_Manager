from django.db import transaction

from activity.services import log_activity
from core.exceptions import DomainError
from core.permissions import can_archive_project, can_create_project
from core.slugs import create_with_unique_slug
from projects.models import Project
from workspaces.models import Workspace


@transaction.atomic
def create_project(*, workspace: Workspace, name: str, description: str, created_by) -> Project:
    if not can_create_project(workspace=workspace, user=created_by):
        raise DomainError("Project creation requires admin access.")

    return create_with_unique_slug(
        model=Project,
        value=name,
        scope={"workspace": workspace},
        create_kwargs={
            "workspace": workspace,
            "name": name,
            "description": description,
            "created_by": created_by,
        },
    )


@transaction.atomic
def archive_project(*, project: Project, actor) -> Project:
    if not can_archive_project(project=project, user=actor):
        raise DomainError("Project archiving requires admin access.")

    if project.is_archived:
        return project

    project.is_archived = True
    project.save(update_fields=["is_archived", "updated_at"])
    log_activity(
        workspace=project.workspace,
        actor=actor,
        action="project_archived",
        target_type="project",
        target_id=project.id,
        metadata={"project_name": project.name},
    )
    return project


@transaction.atomic
def unarchive_project(*, project: Project, actor) -> Project:
    if not can_archive_project(project=project, user=actor):
        raise DomainError("Project archiving requires admin access.")

    if not project.is_archived:
        return project

    project.is_archived = False
    project.save(update_fields=["is_archived", "updated_at"])
    log_activity(
        workspace=project.workspace,
        actor=actor,
        action="project_unarchived",
        target_type="project",
        target_id=project.id,
        metadata={"project_name": project.name},
    )
    return project
