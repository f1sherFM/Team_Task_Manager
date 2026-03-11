from django.contrib import admin

from activity.models import ActivityLog


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("workspace", "actor", "action", "target_type", "target_id", "created_at")
    list_filter = ("action", "target_type", "workspace")
    search_fields = ("workspace__name", "actor__username", "target_id")
