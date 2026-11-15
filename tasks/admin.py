from django.contrib import admin

from tasks.models import Task, TaskChecklistItem, TaskTag


class TaskChecklistItemInline(admin.TabularInline):
    model = TaskChecklistItem
    extra = 1


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
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
