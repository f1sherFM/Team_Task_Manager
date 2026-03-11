from django.contrib import admin

from workspaces.models import Invitation, Membership, Workspace


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "owner", "created_at")
    search_fields = ("name", "slug", "owner__username", "owner__email")
    readonly_fields = ("slug", "created_at", "updated_at")

    def get_readonly_fields(self, request, obj=None):
        if obj is not None:
            return (*self.readonly_fields, "owner")
        return self.readonly_fields


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("workspace", "user", "role", "joined_at")
    list_filter = ("role",)
    search_fields = ("workspace__name", "user__username", "user__email")
    readonly_fields = ("joined_at",)

    def get_readonly_fields(self, request, obj=None):
        if obj is not None:
            return (*self.readonly_fields, "workspace", "user", "role")
        return self.readonly_fields

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.role == "owner":
            return False
        return super().has_delete_permission(request, obj)


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ("workspace", "email", "role", "invited_by", "created_at", "accepted_at")
    list_filter = ("role", "accepted_at")
    search_fields = ("workspace__name", "email", "invited_by__username")
