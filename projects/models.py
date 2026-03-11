from django.conf import settings
from django.db import models

from workspaces.models import Workspace


class Project(models.Model):
    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name="projects",
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_projects",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_archived = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("workspace", "slug"),
                name="unique_project_slug_per_workspace",
            ),
        ]
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name
