from django.http import Http404
from rest_framework import generics, mixins, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from activity.selectors import get_user_activity, get_workspace_activity
from api.permissions import (
    CommentPermission,
    MembershipManagementPermission,
    ProjectArchivePermission,
    ProjectPermission,
    TaskPermission,
    WorkspaceInvitationPermission,
    WorkspaceOwnershipTransferPermission,
    WorkspacePermission,
)
from api.serializers import (
    ActivityLogSerializer,
    CommentSerializer,
    InvitationAcceptSerializer,
    InvitationRevokeSerializer,
    InvitationSerializer,
    MembershipSerializer,
    ProjectArchiveSerializer,
    ProjectSerializer,
    TaskBulkUpdateSerializer,
    TaskSerializer,
    WorkspaceOwnershipTransferSerializer,
    WorkspaceSerializer,
)
from comments.selectors import get_user_comments
from comments.services import soft_delete_comment
from core.exceptions import DomainError
from projects.models import Project
from projects.selectors import get_workspace_project_by_slug
from tasks.models import Task
from tasks.selectors import get_project_task_by_slug
from workspaces.models import Invitation, Membership, Workspace
from workspaces.selectors import (
    get_invitation_by_token,
    get_user_workspace_by_slug,
    get_user_workspaces,
    get_workspace_invitation_by_id,
    get_workspace_invitations,
    get_workspace_membership_by_id,
)
from workspaces.services import remove_membership


class WorkspaceViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = WorkspaceSerializer
    permission_classes = [WorkspacePermission]
    lookup_field = "slug"

    def get_queryset(self):
        return get_user_workspaces(self.request.user)


class ProjectViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = ProjectSerializer
    permission_classes = [ProjectPermission]
    lookup_field = "slug"
    filter_backends = [OrderingFilter]
    ordering_fields = ["created_at"]

    def get_queryset(self):
        from projects.selectors import get_user_projects

        queryset = get_user_projects(self.request.user)
        workspace_slug = self.request.query_params.get("workspace")
        if workspace_slug:
            queryset = queryset.filter(workspace__slug=workspace_slug)
        return queryset


class TaskViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = TaskSerializer
    permission_classes = [TaskPermission]
    lookup_field = "slug"
    filter_backends = [OrderingFilter]
    ordering_fields = ["created_at"]

    def get_queryset(self):
        from tasks.selectors import get_user_tasks

        queryset = get_user_tasks(self.request.user)
        project_slug = self.request.query_params.get("project")
        status_value = self.request.query_params.get("status")
        assignee_id = self.request.query_params.get("assignee")
        if project_slug:
            queryset = queryset.filter(project__slug=project_slug)
        if status_value:
            queryset = queryset.filter(status=status_value)
        if assignee_id:
            queryset = queryset.filter(assignee_id=assignee_id)
        return queryset


class CommentViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = CommentSerializer
    permission_classes = [CommentPermission]

    def get_queryset(self):
        queryset = get_user_comments(self.request.user)
        task_slug = self.request.query_params.get("task")
        if task_slug:
            queryset = queryset.filter(task__slug=task_slug)
        return queryset

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            soft_delete_comment(comment=instance, actor=request.user)
        except DomainError as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        return Response(status=status.HTTP_204_NO_CONTENT)


class ActivityViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = ActivityLogSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [OrderingFilter]
    ordering_fields = ["created_at"]

    def get_queryset(self):
        return get_user_activity(self.request.user)


class WorkspaceActivityAPIView(generics.ListAPIView):
    serializer_class = ActivityLogSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [OrderingFilter]
    ordering_fields = ["created_at"]

    def get_queryset(self):
        try:
            workspace = get_user_workspace_by_slug(
                slug=self.kwargs["slug"],
                user=self.request.user,
            )
        except Workspace.DoesNotExist as exc:
            raise Http404("Workspace not found.") from exc
        return get_workspace_activity(workspace)


class WorkspaceInvitationListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = InvitationSerializer
    permission_classes = [WorkspaceInvitationPermission]

    def get_workspace(self):
        try:
            workspace = get_user_workspace_by_slug(
                slug=self.kwargs["slug"],
                user=self.request.user,
            )
        except Workspace.DoesNotExist as exc:
            raise Http404("Workspace not found.") from exc
        self.check_object_permissions(self.request, workspace)
        return workspace

    def get_queryset(self):
        return get_workspace_invitations(self.get_workspace())

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["workspace"] = self.get_workspace()
        return context


class InvitationAcceptAPIView(generics.CreateAPIView):
    serializer_class = InvitationAcceptSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["token"] = self.kwargs["token"]
        return context

    def create(self, request, *args, **kwargs):
        try:
            get_invitation_by_token(token=kwargs["token"])
        except Invitation.DoesNotExist as exc:
            raise Http404("Invitation not found.") from exc
        return super().create(request, *args, **kwargs)


class WorkspaceMembershipDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = MembershipSerializer
    permission_classes = [MembershipManagementPermission]

    def get_object(self):
        try:
            workspace = get_user_workspace_by_slug(
                slug=self.kwargs["slug"],
                user=self.request.user,
            )
            membership = get_workspace_membership_by_id(
                workspace=workspace,
                membership_id=self.kwargs["membership_id"],
            )
        except (Workspace.DoesNotExist, Membership.DoesNotExist) as exc:
            raise Http404("Membership not found.") from exc
        self.check_object_permissions(self.request, membership)
        return membership

    def destroy(self, request, *args, **kwargs):
        membership = self.get_object()
        try:
            remove_membership(membership=membership, actor=request.user)
        except DomainError as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        return Response(status=status.HTTP_204_NO_CONTENT)


class WorkspaceInvitationRevokeAPIView(generics.DestroyAPIView):
    serializer_class = InvitationRevokeSerializer
    permission_classes = [WorkspaceInvitationPermission]

    def get_object(self):
        try:
            workspace = get_user_workspace_by_slug(
                slug=self.kwargs["slug"],
                user=self.request.user,
            )
            invitation = get_workspace_invitation_by_id(
                workspace=workspace,
                invitation_id=self.kwargs["invitation_id"],
            )
        except (Workspace.DoesNotExist, Invitation.DoesNotExist) as exc:
            raise Http404("Invitation not found.") from exc
        self.check_object_permissions(self.request, workspace)
        return invitation

    def destroy(self, request, *args, **kwargs):
        invitation = self.get_object()
        serializer = self.get_serializer(data={})
        serializer.context["invitation"] = invitation
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class WorkspaceOwnershipTransferAPIView(generics.CreateAPIView):
    serializer_class = WorkspaceOwnershipTransferSerializer
    permission_classes = [WorkspaceOwnershipTransferPermission]

    def get_workspace(self):
        try:
            workspace = get_user_workspace_by_slug(
                slug=self.kwargs["slug"],
                user=self.request.user,
            )
        except Workspace.DoesNotExist as exc:
            raise Http404("Workspace not found.") from exc
        self.check_object_permissions(self.request, workspace)
        return workspace

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["workspace"] = self.get_workspace()
        return context

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        workspace = serializer.save()
        return Response(serializer.to_representation(workspace), status=status.HTTP_200_OK)


class ProjectDetailAPIView(generics.RetrieveAPIView):
    serializer_class = ProjectSerializer
    permission_classes = [ProjectPermission]

    def get_object(self):
        try:
            project = get_workspace_project_by_slug(
                workspace_slug=self.kwargs["workspace_slug"],
                project_slug=self.kwargs["project_slug"],
                user=self.request.user,
            )
        except Project.DoesNotExist as exc:
            raise Http404("Project not found.") from exc
        self.check_object_permissions(self.request, project)
        return project


class ProjectArchiveAPIView(generics.CreateAPIView):
    serializer_class = ProjectArchiveSerializer
    permission_classes = [ProjectArchivePermission]
    action = "archive"

    def get_project(self):
        try:
            project = get_workspace_project_by_slug(
                workspace_slug=self.kwargs["workspace_slug"],
                project_slug=self.kwargs["project_slug"],
                user=self.request.user,
            )
        except Project.DoesNotExist as exc:
            raise Http404("Project not found.") from exc
        self.check_object_permissions(self.request, project)
        return project

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["project"] = self.get_project()
        context["action"] = self.action
        return context

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data={})
        serializer.is_valid(raise_exception=True)
        project = serializer.save()
        return Response(serializer.to_representation(project), status=status.HTTP_200_OK)


class ProjectUnarchiveAPIView(ProjectArchiveAPIView):
    action = "unarchive"


class TaskDetailAPIView(generics.RetrieveUpdateAPIView):
    serializer_class = TaskSerializer
    permission_classes = [TaskPermission]

    def get_object(self):
        try:
            task = get_project_task_by_slug(
                workspace_slug=self.kwargs["workspace_slug"],
                project_slug=self.kwargs["project_slug"],
                task_slug=self.kwargs["task_slug"],
                user=self.request.user,
            )
        except Task.DoesNotExist as exc:
            raise Http404("Task not found.") from exc
        self.check_object_permissions(self.request, task)
        return task


class TaskBulkUpdateAPIView(generics.CreateAPIView):
    serializer_class = TaskBulkUpdateSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.save()
        return Response(serializer.to_representation(payload), status=status.HTTP_200_OK)
