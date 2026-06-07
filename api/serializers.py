from django.contrib.auth import get_user_model
from rest_framework import serializers

from activity.models import ActivityLog
from comments.models import Comment
from comments.services import add_comment
from core.exceptions import DomainError
from projects.models import Project
from projects.selectors import get_workspace_project_by_slug
from projects.services import archive_project, create_project, unarchive_project
from tasks.models import Task
from tasks.selectors import get_project_task_by_slug
from tasks.services import UNSET, create_task, update_task
from workspaces.models import Invitation, Membership, Workspace
from workspaces.selectors import (
    get_invitation_by_token,
    get_user_workspace_by_slug,
    get_workspace_membership_by_id,
)
from workspaces.services import (
    accept_invitation,
    change_membership_role,
    create_invitation,
    create_workspace,
    revoke_invitation,
    transfer_workspace_ownership,
)

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
        read_only_fields = (
            "slug",
            "workspace",
            "created_by",
            "created_at",
            "updated_at",
            "is_archived",
        )

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

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if self.instance is None:
            return attrs

        allowed_fields = {"title", "description", "priority", "due_date", "status", "assignee_id"}
        invalid_fields = set(self.initial_data) - allowed_fields
        if invalid_fields:
            raise serializers.ValidationError(
                {
                    field_name: ["This field cannot be updated."]
                    for field_name in sorted(invalid_fields)
                }
            )
        return attrs

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
                title=validated_data["title"],
                description=validated_data.get("description", ""),
                priority=validated_data["priority"],
                due_date=validated_data.get("due_date"),
            )
        except (Project.DoesNotExist, DomainError) as exc:
            raise serializers.ValidationError({"detail": str(exc)}) from exc

    def update(self, instance, validated_data):
        request = self.context["request"]
        assignee_id = validated_data.pop("assignee_id", UNSET)
        try:
            assignee = UNSET
            if assignee_id is not UNSET:
                assignee = User.objects.filter(id=assignee_id).first() if assignee_id else None
            return update_task(
                task=instance,
                actor=request.user,
                title=validated_data.get("title", UNSET),
                description=validated_data.get("description", UNSET),
                priority=validated_data.get("priority", UNSET),
                due_date=validated_data.get("due_date", UNSET),
                assignee=assignee,
                status=validated_data.get("status", UNSET),
            )
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
        fields = (
            "id",
            "workspace",
            "actor",
            "action",
            "target_type",
            "target_id",
            "metadata",
            "created_at",
        )


class InvitationSerializer(serializers.ModelSerializer):
    invited_by = serializers.CharField(source="invited_by.username", read_only=True)
    workspace = serializers.CharField(source="workspace.slug", read_only=True)

    class Meta:
        model = Invitation
        fields = (
            "email",
            "role",
            "token",
            "workspace",
            "invited_by",
            "created_at",
            "expires_at",
            "accepted_at",
        )
        read_only_fields = (
            "token",
            "workspace",
            "invited_by",
            "created_at",
            "expires_at",
            "accepted_at",
        )

    def create(self, validated_data):
        request = self.context["request"]
        workspace = self.context["workspace"]
        try:
            return create_invitation(
                workspace=workspace,
                email=validated_data["email"],
                role=validated_data["role"],
                invited_by=request.user,
            )
        except DomainError as exc:
            raise serializers.ValidationError({"detail": str(exc)}) from exc


class MembershipSerializer(serializers.ModelSerializer):
    user = serializers.CharField(source="user.username", read_only=True)
    user_id = serializers.IntegerField(source="user.id", read_only=True)

    class Meta:
        model = Membership
        fields = ("id", "user", "user_id", "role", "joined_at")
        read_only_fields = ("id", "user", "user_id", "joined_at")

    def update(self, instance, validated_data):
        request = self.context["request"]
        try:
            return change_membership_role(
                membership=instance,
                role=validated_data["role"],
                actor=request.user,
            )
        except DomainError as exc:
            raise serializers.ValidationError({"detail": str(exc)}) from exc


class WorkspaceOwnershipTransferSerializer(serializers.Serializer):
    membership_id = serializers.IntegerField(min_value=1)

    def create(self, validated_data):
        request = self.context["request"]
        workspace = self.context["workspace"]
        try:
            membership = get_workspace_membership_by_id(
                workspace=workspace,
                membership_id=validated_data["membership_id"],
            )
            return transfer_workspace_ownership(
                workspace=workspace,
                new_owner_membership=membership,
                actor=request.user,
            )
        except (Membership.DoesNotExist, DomainError) as exc:
            raise serializers.ValidationError({"detail": str(exc)}) from exc

    def to_representation(self, instance):
        return {
            "workspace": instance.slug,
            "owner": instance.owner.username,
        }


class InvitationAcceptSerializer(serializers.Serializer):
    token = serializers.UUIDField(read_only=True)
    workspace = serializers.CharField(read_only=True)
    role = serializers.CharField(read_only=True)
    accepted_at = serializers.DateTimeField(read_only=True)

    def create(self, validated_data):
        request = self.context["request"]
        token = self.context["token"]
        try:
            invitation = get_invitation_by_token(token=token)
        except Invitation.DoesNotExist as exc:
            raise serializers.ValidationError({"detail": "Invitation not found."}) from exc

        try:
            accept_invitation(invitation=invitation, user=request.user)
        except DomainError as exc:
            raise serializers.ValidationError({"detail": str(exc)}) from exc

        invitation.refresh_from_db()
        return invitation

    def to_representation(self, instance):
        return {
            "token": str(instance.token),
            "workspace": instance.workspace.slug,
            "role": instance.role,
            "accepted_at": instance.accepted_at,
        }


class ProjectArchiveSerializer(serializers.Serializer):
    slug = serializers.CharField(read_only=True)
    is_archived = serializers.BooleanField(read_only=True)

    def create(self, validated_data):
        request = self.context["request"]
        project = self.context["project"]
        action = self.context["action"]
        if action == "archive":
            return archive_project(project=project, actor=request.user)
        return unarchive_project(project=project, actor=request.user)

    def to_representation(self, instance):
        return {
            "slug": instance.slug,
            "is_archived": instance.is_archived,
        }


class InvitationRevokeSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)

    def create(self, validated_data):
        request = self.context["request"]
        invitation = self.context["invitation"]
        try:
            revoke_invitation(invitation=invitation, actor=request.user)
        except DomainError as exc:
            raise serializers.ValidationError({"detail": str(exc)}) from exc
        return invitation
