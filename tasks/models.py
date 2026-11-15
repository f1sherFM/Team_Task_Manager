from django.conf import settings
from django.db import models

from projects.models import Project
from tasks.validators import validate_hex_color
from workspaces.models import Workspace


class TaskStatus(models.TextChoices):
    TODO = "todo", "To do"
    IN_PROGRESS = "in_progress", "In progress"
    DONE = "done", "Done"


class TaskPriority(models.TextChoices):
    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"


class TaskTag(models.Model):
    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name="tags",
    )
    name = models.CharField(max_length=50)
    slug = models.SlugField(max_length=50)
    color = models.CharField(
        max_length=7,
        default="#6c757d",
        validators=[validate_hex_color],
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("workspace", "slug"),
                name="unique_tag_slug_per_workspace",
            ),
        ]
        ordering = ("name", "id")

    def __str__(self) -> str:
        return f"{self.name} ({self.workspace.slug})"


class Task(models.Model):
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=TaskStatus.choices,
        default=TaskStatus.TODO,
    )
    priority = models.CharField(
        max_length=20,
        choices=TaskPriority.choices,
        default=TaskPriority.MEDIUM,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_tasks",
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="assigned_tasks",
        blank=True,
        null=True,
    )
    due_date = models.DateField(blank=True, null=True)
    is_archived = models.BooleanField(default=False)
    tags = models.ManyToManyField(
        TaskTag,
        related_name="tasks",
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("project", "slug"),
                name="unique_task_slug_per_project",
            ),
        ]
        indexes = [
            models.Index(fields=["project", "status"]),
            models.Index(fields=["project", "is_archived"]),
        ]
        ordering = ("created_at",)

    def __str__(self) -> str:
        return self.title


class TaskChecklistItem(models.Model):
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="checklist_items",
    )
    text = models.CharField(max_length=255)
    is_completed = models.BooleanField(default=False)
    position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("position", "id")

    def __str__(self) -> str:
        status = "x" if self.is_completed else " "
        return f"[{status}] {self.text}"
