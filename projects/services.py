from django.db import transaction

from core.exceptions import DomainError
from core.permissions import can_create_project
from core.slugs import generate_unique_slug
from projects.models import Project
from workspaces.models import Workspace


@transaction.atomic
def create_project(*, workspace: Workspace, name: str, description: str, created_by) -> Project:
    if not can_create_project(workspace=workspace, user=created_by):
        raise DomainError("Project creation requires admin access.")

    slug = generate_unique_slug(
        model=Project,
        value=name,
        scope={"workspace": workspace},
    )
    return Project.objects.create(
        workspace=workspace,
        name=name,
        slug=slug,
        description=description,
        created_by=created_by,
    )
