from django.contrib import admin

from comments.models import Comment


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("id", "task", "author", "is_deleted", "created_at")
    list_filter = ("is_deleted",)
    search_fields = ("task__title", "author__username", "text")
