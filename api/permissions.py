from rest_framework.permissions import SAFE_METHODS, BasePermission

from core.permissions import (
    can_archive_project,
    can_assign_task,
    can_change_task_status,
    can_delete_comment,
    can_manage_invitations,
    can_manage_membership,
    can_transfer_workspace_ownership,
    can_update_task,
    can_view_project,
    can_view_task,
    can_view_workspace,
)


class WorkspacePermission(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        return can_view_workspace(workspace=obj, user=request.user)


class ProjectPermission(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        return can_view_project(project=obj, user=request.user)


class TaskPermission(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return can_view_task(task=obj, user=request.user)

        allowed = can_update_task(task=obj, user=request.user)
        if "assignee" in request.data or "assignee_id" in request.data:
            allowed = allowed and can_assign_task(task=obj, user=request.user)
        if "status" in request.data:
            allowed = allowed and can_change_task_status(task=obj, user=request.user)
        return allowed


class CommentPermission(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return can_view_task(task=obj.task, user=request.user)
        return can_delete_comment(comment=obj, user=request.user)


class WorkspaceInvitationPermission(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        return can_manage_invitations(workspace=obj, user=request.user)


class ProjectArchivePermission(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        return can_archive_project(project=obj, user=request.user)


class MembershipManagementPermission(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        return can_manage_membership(membership=obj, user=request.user)


class WorkspaceOwnershipTransferPermission(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        return can_transfer_workspace_ownership(workspace=obj, user=request.user)
