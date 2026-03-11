from django.http import Http404
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from activity.models import ActivityLog
from activity.selectors import get_workspace_activity
from api.permissions import CommentPermission, ProjectPermission, TaskPermission, WorkspacePermission
from api.serializers import (
    ActivityLogSerializer,
    CommentSerializer,
    ProjectSerializer,
    TaskSerializer,
    WorkspaceSerializer,
)
from comments.models import Comment
from comments.services import soft_delete_comment
from core.exceptions import DomainError
from projects.models import Project
from projects.selectors import get_project_by_slug
from tasks.models import Task
from tasks.selectors import get_task_by_slug
from workspaces.models import Workspace
from workspaces.selectors import get_user_workspace_by_slug, get_user_workspaces


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
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = ProjectSerializer
    permission_classes = [ProjectPermission]
    lookup_field = "slug"

    def get_queryset(self):
        queryset = (
            Project.objects.filter(workspace__memberships__user=self.request.user)
            .select_related("workspace", "created_by", "workspace__owner")
            .distinct()
        )
        workspace_slug = self.request.query_params.get("workspace")
        if workspace_slug:
            queryset = queryset.filter(workspace__slug=workspace_slug)
        return queryset


class TaskViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = TaskSerializer
    permission_classes = [TaskPermission]
    lookup_field = "slug"

    def get_queryset(self):
        queryset = (
            Task.objects.filter(project__workspace__memberships__user=self.request.user)
            .select_related("project", "project__workspace", "created_by", "assignee")
            .distinct()
        )
        project_slug = self.request.query_params.get("project")
        if project_slug:
            queryset = queryset.filter(project__slug=project_slug)
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
        queryset = (
            Comment.objects.filter(
                task__project__workspace__memberships__user=self.request.user
            )
            .select_related("task", "author", "task__project", "task__project__workspace")
            .distinct()
        )
        task_slug = self.request.query_params.get("task")
        if task_slug:
            queryset = queryset.filter(task__slug=task_slug)
        return queryset

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            soft_delete_comment(comment=instance, actor=request.user)
        except DomainError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ActivityViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = ActivityLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            ActivityLog.objects.filter(
                workspace__memberships__user=self.request.user
            )
            .select_related("workspace", "actor")
            .distinct()
            .order_by("-created_at")
        )


class WorkspaceActivityAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        try:
            workspace = get_user_workspace_by_slug(slug=slug, user=request.user)
        except Workspace.DoesNotExist as exc:
            raise Http404("Workspace not found.") from exc

        serializer = ActivityLogSerializer(get_workspace_activity(workspace), many=True)
        return Response(serializer.data)
