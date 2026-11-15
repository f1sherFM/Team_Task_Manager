from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError

from core.exceptions import DomainError
from tasks.models import Task, TaskChecklistItem, TaskTag
from tasks.services import set_task_tags


class TaskAdminForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        project = cleaned_data.get("project") or (
            self.instance.project if self.instance.pk else None
        )
        tags = cleaned_data.get("tags")
        if project and tags:
            workspace = project.workspace
            invalid_tags = [tag.name for tag in tags if tag.workspace_id != workspace.id]
            if invalid_tags:
                raise ValidationError(
                    {
                        "tags": (
                            f"Tags do not belong to the task workspace: {', '.join(invalid_tags)}"
                        )
                    }
                )
        return cleaned_data


class TaskChecklistItemInline(admin.TabularInline):
    model = TaskChecklistItem
    extra = 1


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    form = TaskAdminForm
    list_display = (
        "title",
        "project",
        "status",
        "priority",
        "assignee",
        "due_date",
        "is_archived",
    )
    list_filter = ("status", "priority", "is_archived", "project")
    search_fields = ("title", "slug", "project__name", "created_by__username")
    filter_horizontal = ("tags",)
    inlines = [TaskChecklistItemInline]

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "tags":
            object_id = (
                request.resolver_match.kwargs.get("object_id")
                if request.resolver_match
                else None
            )
            if object_id:
                try:
                    task = Task.objects.select_related("project__workspace").get(pk=object_id)
                    kwargs["queryset"] = TaskTag.objects.filter(workspace=task.project.workspace)
                except (Task.DoesNotExist, ValueError):
                    kwargs["queryset"] = TaskTag.objects.none()
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        tags = form.cleaned_data.get("tags")
        if tags is not None:
            workspace = form.instance.project.workspace
            for tag in tags:
                if tag.workspace_id != workspace.id:
                    raise ValidationError(
                        f"Tag '{tag.name}' does not belong to workspace '{workspace.name}'."
                    )
            try:
                set_task_tags(task=form.instance, tags=list(tags), actor=request.user)
            except DomainError:
                form.instance.tags.set(tags)


@admin.register(TaskTag)
class TaskTagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "workspace", "color", "created_at")
    list_filter = ("workspace",)
    search_fields = ("name", "slug", "workspace__name")


@admin.register(TaskChecklistItem)
class TaskChecklistItemAdmin(admin.ModelAdmin):
    list_display = ("text", "task", "position", "is_completed", "created_at")
    list_filter = ("is_completed",)
    search_fields = ("text", "task__title")
