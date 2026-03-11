from rest_framework import serializers

from activity.models import ActivityLog
from comments.models import Comment
from comments.services import add_comment
from core.exceptions import DomainError
from django.contrib.auth import get_user_model
from projects.models import Project
from projects.selectors import get_workspace_project_by_slug
from projects.services import create_project
from tasks.models import Task
from tasks.selectors import get_project_task_by_slug
from tasks.services import assign_task, change_task_status, create_task
from workspaces.models import Workspace
from workspaces.selectors import get_user_workspace_by_slug
from workspaces.services import create_workspace


User = get_user_model()


class WorkspaceSerializer(serializers.ModelSerializer):
    owner = serializers.CharField(source="owner.username", read_only=True)

    class Meta:
        model = Workspace
        fields = ("name", "slug", "owner", "created_at", "updated_at")
        read_only_fields = ("slug", "owner", "created_at", "updated_at")

    def create(self, validated_data):
        request = self.context["request"]
        return create_workspace(owner=request.user, name=validated_data["name"])


class ProjectSerializer(serializers.ModelSerializer):
    workspace_slug = serializers.SlugField(write_only=True)
    workspace = serializers.CharField(source="workspace.slug", read_only=True)
    created_by = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = Project
        fields = (
            "name",
            "slug",
            "description",
            "workspace",
            "workspace_slug",
            "created_by",
            "created_at",
            "updated_at",
            "is_archived",
        )
        read_only_fields = ("slug", "workspace", "created_by", "created_at", "updated_at", "is_archived")

    def create(self, validated_data):
        workspace_slug = validated_data.pop("workspace_slug")
        request = self.context["request"]
        try:
            workspace = get_user_workspace_by_slug(
                slug=workspace_slug,
                user=request.user,
            )
            return create_project(workspace=workspace, created_by=request.user, **validated_data)
        except (Workspace.DoesNotExist, DomainError) as exc:
            raise serializers.ValidationError({"detail": str(exc)}) from exc


class TaskSerializer(serializers.ModelSerializer):
    workspace_slug = serializers.SlugField(write_only=True, required=False)
    project_slug = serializers.SlugField(write_only=True, required=False)
    project = serializers.CharField(source="project.slug", read_only=True)
    created_by = serializers.CharField(source="created_by.username", read_only=True)
    assignee = serializers.CharField(source="assignee.username", read_only=True)
    assignee_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = Task
        fields = (
            "title",
            "slug",
            "description",
            "status",
            "priority",
            "project",
            "workspace_slug",
            "project_slug",
            "created_by",
            "assignee",
            "assignee_id",
            "due_date",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("slug", "project", "created_by", "assignee", "created_at", "updated_at")

    def create(self, validated_data):
        workspace_slug = validated_data.pop("workspace_slug", None)
        project_slug = validated_data.pop("project_slug", None)
        if not workspace_slug or not project_slug:
            raise serializers.ValidationError(
                {"detail": "Both workspace_slug and project_slug are required."}
            )
        assignee_id = validated_data.pop("assignee_id", None)
        request = self.context["request"]
        try:
            project = get_workspace_project_by_slug(
                workspace_slug=workspace_slug,
                project_slug=project_slug,
                user=request.user,
            )
            assignee = User.objects.filter(id=assignee_id).first() if assignee_id else None
            return create_task(
                project=project,
                created_by=request.user,
                assignee=assignee,
                **validated_data,
            )
        except (Project.DoesNotExist, DomainError) as exc:
            raise serializers.ValidationError({"detail": str(exc)}) from exc

    def update(self, instance, validated_data):
        request = self.context["request"]
        assignee_id = validated_data.pop("assignee_id", serializers.empty)
        try:
            if assignee_id is not serializers.empty:
                assignee = User.objects.filter(id=assignee_id).first() if assignee_id else None
                instance = assign_task(task=instance, assignee=assignee, actor=request.user)
            if "status" in validated_data:
                instance = change_task_status(task=instance, status=validated_data["status"], actor=request.user)
            return instance
        except DomainError as exc:
            raise serializers.ValidationError({"detail": str(exc)}) from exc


class CommentSerializer(serializers.ModelSerializer):
    workspace_slug = serializers.SlugField(write_only=True)
    project_slug = serializers.SlugField(write_only=True)
    task_slug = serializers.SlugField(write_only=True)
    author = serializers.CharField(source="author.username", read_only=True)
    text = serializers.SerializerMethodField()
    raw_text = serializers.CharField(write_only=True, source="text")

    class Meta:
        model = Comment
        fields = (
            "id",
            "workspace_slug",
            "project_slug",
            "task_slug",
            "author",
            "text",
            "raw_text",
            "created_at",
            "updated_at",
            "is_deleted",
        )
        read_only_fields = ("id", "author", "text", "created_at", "updated_at", "is_deleted")

    def get_text(self, obj):
        return "[deleted]" if obj.is_deleted else obj.text

    def create(self, validated_data):
        workspace_slug = validated_data.pop("workspace_slug")
        project_slug = validated_data.pop("project_slug")
        task_slug = validated_data.pop("task_slug")
        request = self.context["request"]
        try:
            task = get_project_task_by_slug(
                workspace_slug=workspace_slug,
                project_slug=project_slug,
                task_slug=task_slug,
                user=request.user,
            )
            return add_comment(task=task, author=request.user, text=validated_data["text"])
        except (Task.DoesNotExist, DomainError) as exc:
            raise serializers.ValidationError({"detail": str(exc)}) from exc


class ActivityLogSerializer(serializers.ModelSerializer):
    actor = serializers.CharField(source="actor.username", read_only=True)
    workspace = serializers.CharField(source="workspace.slug", read_only=True)

    class Meta:
        model = ActivityLog
        fields = ("id", "workspace", "actor", "action", "target_type", "target_id", "metadata", "created_at")
