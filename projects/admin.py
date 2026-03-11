from django.contrib import admin

from projects.models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "workspace", "created_by", "is_archived", "created_at")
    list_filter = ("is_archived", "workspace")
    search_fields = ("name", "slug", "workspace__name", "created_by__username")
