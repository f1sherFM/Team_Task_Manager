from django.db import transaction

from core.exceptions import DomainError
from core.permissions import can_create_project
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
