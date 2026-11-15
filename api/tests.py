from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from activity.models import ActivityLog
from activity.services import log_activity
from comments.services import add_comment
from projects.models import Project
from projects.services import archive_project, create_project
from tasks.models import Task, TaskChecklistItem, TaskTag
from tasks.services import (
    add_checklist_item,
    assign_task,
    create_task,
    create_task_tag,
)
from workspaces.models import Invitation, Membership, MembershipRole
from workspaces.services import create_invitation, create_workspace

User = get_user_model()


class ApiPermissionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(username="owner", password="secret123")
        self.admin = User.objects.create_user(username="admin", password="secret123")
        self.member = User.objects.create_user(username="member", password="secret123")
        self.outsider = User.objects.create_user(username="outsider", password="secret123")

        self.workspace = create_workspace(owner=self.owner, name="Engineering")
        Membership.objects.create(
            workspace=self.workspace,
            user=self.admin,
            role=MembershipRole.ADMIN,
        )
        Membership.objects.create(
            workspace=self.workspace,
            user=self.member,
            role=MembershipRole.MEMBER,
        )
        self.project = create_project(
            workspace=self.workspace,
            name="Backend",
            description="Backend domain",
            created_by=self.owner,
        )
        self.task = create_task(
            project=self.project,
            title="Ship API",
            description="",
            priority="medium",
            due_date=None,
            assignee=None,
            created_by=self.member,
        )
        self.comment = add_comment(task=self.task, author=self.member, text="Visible comment")

    def test_workspace_api_only_lists_user_workspaces(self):
        self.client.force_authenticate(self.member)

        response = self.client.get("/api/workspaces/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["slug"], self.workspace.slug)

    def test_outsider_cannot_access_workspace_detail_api(self):
        self.client.force_authenticate(self.outsider)

        response = self.client.get(f"/api/workspaces/{self.workspace.slug}/")

        self.assertEqual(response.status_code, 404)

    def test_outsider_cannot_access_project_detail_api(self):
        self.client.force_authenticate(self.outsider)

        response = self.client.get(
            f"/api/workspaces/{self.workspace.slug}/projects/{self.project.slug}/"
        )

        self.assertEqual(response.status_code, 404)

    def test_member_cannot_assign_task_via_api(self):
        self.client.force_authenticate(self.member)

        response = self.client.patch(
            f"/api/workspaces/{self.workspace.slug}/projects/{self.project.slug}/tasks/{self.task.slug}/",
            {"assignee_id": self.admin.id},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_assignee_can_change_task_status_via_api(self):
        assign_task(task=self.task, assignee=self.member, actor=self.admin)
        self.client.force_authenticate(self.member)

        response = self.client.patch(
            f"/api/workspaces/{self.workspace.slug}/projects/{self.project.slug}/tasks/{self.task.slug}/",
            {"status": "done"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "done")

    def test_deleted_comment_api_hides_original_text(self):
        self.client.force_authenticate(self.member)
        self.client.delete(f"/api/comments/{self.comment.id}/")

        response = self.client.get("/api/comments/", {"task": self.task.slug})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"][0]["text"], "[deleted]")

    def test_comments_api_supports_author_and_deleted_filters(self):
        self.client.force_authenticate(self.member)
        second_comment = add_comment(task=self.task, author=self.owner, text="Owner note")
        self.client.delete(f"/api/comments/{self.comment.id}/")

        response = self.client.get(
            "/api/comments/",
            {"author": self.owner.id, "is_deleted": "false", "q": "owner"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], second_comment.id)

    def test_project_create_api_rejects_member_without_admin_role(self):
        self.client.force_authenticate(self.member)

        response = self.client.post(
            "/api/projects/",
            {
                "name": "Forbidden project",
                "description": "No access",
                "workspace_slug": self.workspace.slug,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Project creation requires admin access.")

    def test_workspace_activity_api_uses_paginated_list_format(self):
        self.client.force_authenticate(self.member)
        initial_count = ActivityLog.objects.filter(workspace=self.workspace).count()
        for index in range(25):
            log_activity(
                workspace=self.workspace,
                actor=self.member,
                action=f"task_event_{index}",
                target_type="task",
                target_id=str(index),
                metadata={"index": index},
            )

        response = self.client.get(f"/api/workspaces/{self.workspace.slug}/activity/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], initial_count + 25)
        self.assertEqual(len(response.data["results"]), 20)

    def test_projects_api_supports_created_at_ordering(self):
        self.client.force_authenticate(self.member)
        older_project = create_project(
            workspace=self.workspace,
            name="Older project",
            description="Older",
            created_by=self.owner,
        )
        newer_project = create_project(
            workspace=self.workspace,
            name="Newer project",
            description="Newer",
            created_by=self.owner,
        )
        base_time = timezone.now()
        Project.objects.filter(workspace=self.workspace).update(created_at=base_time)
        Project.objects.filter(id=older_project.id).update(created_at=base_time - timedelta(days=1))
        Project.objects.filter(id=newer_project.id).update(created_at=base_time + timedelta(days=1))

        response = self.client.get(
            "/api/projects/",
            {"ordering": "-created_at", "workspace": self.workspace.slug},
        )

        self.assertEqual(response.status_code, 200)
        returned_slugs = [item["slug"] for item in response.data["results"]]
        self.assertLess(
            returned_slugs.index(newer_project.slug),
            returned_slugs.index(older_project.slug),
        )

    def test_projects_api_filters_by_archive_state_and_search(self):
        self.client.force_authenticate(self.member)
        archived_project = create_project(
            workspace=self.workspace,
            name="Legacy Console",
            description="Old reporting surface",
            created_by=self.owner,
        )
        active_project = create_project(
            workspace=self.workspace,
            name="Analytics Hub",
            description="Current analytics work",
            created_by=self.owner,
        )
        archive_project(project=archived_project, actor=self.owner)

        response = self.client.get(
            "/api/projects/",
            {"workspace": self.workspace.slug, "is_archived": "true", "q": "legacy"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["slug"], archived_project.slug)
        self.assertNotEqual(response.data["results"][0]["slug"], active_project.slug)

    def test_tasks_api_supports_created_at_ordering(self):
        self.client.force_authenticate(self.member)
        older_task = create_task(
            project=self.project,
            title="Older task",
            description="",
            priority="medium",
            due_date=None,
            assignee=None,
            created_by=self.member,
        )
        newer_task = create_task(
            project=self.project,
            title="Newer task",
            description="",
            priority="medium",
            due_date=None,
            assignee=None,
            created_by=self.member,
        )
        base_time = timezone.now()
        Task.objects.filter(project=self.project).update(created_at=base_time)
        Task.objects.filter(id=older_task.id).update(created_at=base_time - timedelta(days=1))
        Task.objects.filter(id=newer_task.id).update(created_at=base_time + timedelta(days=1))

        response = self.client.get(
            "/api/tasks/",
            {"ordering": "-created_at", "project": self.project.slug},
        )

        self.assertEqual(response.status_code, 200)
        returned_slugs = [item["slug"] for item in response.data["results"]]
        self.assertLess(
            returned_slugs.index(newer_task.slug),
            returned_slugs.index(older_task.slug),
        )

    def test_tasks_api_supports_priority_due_date_and_search_filters(self):
        self.client.force_authenticate(self.member)
        target_task = create_task(
            project=self.project,
            title="Prepare release notes",
            description="Write the release notes draft",
            priority="high",
            due_date=timezone.localdate() + timedelta(days=1),
            assignee=None,
            created_by=self.member,
        )
        other_task = create_task(
            project=self.project,
            title="Refactor filters",
            description="Background cleanup",
            priority="low",
            due_date=timezone.localdate() + timedelta(days=10),
            assignee=None,
            created_by=self.member,
        )

        response = self.client.get(
            "/api/tasks/",
            {
                "workspace": self.workspace.slug,
                "priority": "high",
                "due_before": str(timezone.localdate() + timedelta(days=2)),
                "q": "release",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["slug"], target_task.slug)
        self.assertNotEqual(response.data["results"][0]["slug"], other_task.slug)

    def test_tasks_api_supports_overdue_filter(self):
        self.client.force_authenticate(self.member)
        overdue_task = create_task(
            project=self.project,
            title="Overdue task",
            description="Late work",
            priority="medium",
            due_date=timezone.localdate() - timedelta(days=1),
            assignee=None,
            created_by=self.member,
        )
        current_task = create_task(
            project=self.project,
            title="Current task",
            description="On track",
            priority="medium",
            due_date=timezone.localdate() + timedelta(days=2),
            assignee=None,
            created_by=self.member,
        )

        response = self.client.get("/api/tasks/", {"is_overdue": "true"})

        self.assertEqual(response.status_code, 200)
        slugs = [item["slug"] for item in response.data["results"]]
        self.assertIn(overdue_task.slug, slugs)
        self.assertNotIn(current_task.slug, slugs)

    def test_activity_api_supports_created_at_ordering(self):
        self.client.force_authenticate(self.member)
        older = log_activity(
            workspace=self.workspace,
            actor=self.member,
            action="older_event",
            target_type="task",
            target_id="older",
            metadata={},
        )
        newer = log_activity(
            workspace=self.workspace,
            actor=self.member,
            action="newer_event",
            target_type="task",
            target_id="newer",
            metadata={},
        )
        base_time = timezone.now()
        ActivityLog.objects.filter(workspace=self.workspace).update(created_at=base_time)
        ActivityLog.objects.filter(id=older.id).update(created_at=base_time - timedelta(days=1))
        ActivityLog.objects.filter(id=newer.id).update(created_at=base_time + timedelta(days=1))

        response = self.client.get("/api/activity/", {"ordering": "created_at"})

        self.assertEqual(response.status_code, 200)
        actions = [item["action"] for item in response.data["results"]]
        self.assertLess(actions.index("older_event"), actions.index("newer_event"))

    def test_activity_api_supports_actor_action_and_target_filters(self):
        self.client.force_authenticate(self.member)
        log_activity(
            workspace=self.workspace,
            actor=self.member,
            action="task_status_changed",
            target_type="task",
            target_id="target-1",
            metadata={},
        )
        log_activity(
            workspace=self.workspace,
            actor=self.admin,
            action="project_archived",
            target_type="project",
            target_id="target-2",
            metadata={},
        )

        response = self.client.get(
            "/api/activity/",
            {
                "workspace": self.workspace.slug,
                "actor": self.admin.id,
                "action": "project_archived",
                "target_type": "project",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["action"], "project_archived")

    def test_tasks_api_filters_by_status(self):
        self.client.force_authenticate(self.member)
        in_progress_task = create_task(
            project=self.project,
            title="In progress task",
            description="",
            priority="medium",
            due_date=None,
            assignee=None,
            created_by=self.member,
        )
        assign_task(task=in_progress_task, assignee=self.member, actor=self.admin)
        self.client.patch(
            f"/api/workspaces/{self.workspace.slug}/projects/{self.project.slug}/tasks/{in_progress_task.slug}/",
            {"status": "in_progress"},
            format="json",
        )

        response = self.client.get("/api/tasks/", {"status": "in_progress"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["slug"], in_progress_task.slug)

    def test_tasks_api_filters_by_assignee(self):
        self.client.force_authenticate(self.member)
        assigned_task = create_task(
            project=self.project,
            title="Assigned task",
            description="",
            priority="medium",
            due_date=None,
            assignee=None,
            created_by=self.member,
        )
        assign_task(task=assigned_task, assignee=self.admin, actor=self.admin)

        response = self.client.get("/api/tasks/", {"assignee": self.admin.id})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["slug"], assigned_task.slug)

    def test_tasks_api_rejects_invalid_due_before_filter(self):
        self.client.force_authenticate(self.member)

        response = self.client.get("/api/tasks/", {"due_before": "11-06-2026"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["detail"],
            "Invalid date value for due_before. Use YYYY-MM-DD.",
        )

    def test_task_create_api_returns_validation_error_for_invalid_payload(self):
        self.client.force_authenticate(self.member)

        response = self.client.post(
            "/api/tasks/",
            {
                "title": "Invalid task",
                "priority": "urgent",
                "workspace_slug": self.workspace.slug,
                "project_slug": self.project.slug,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("priority", response.data)

    def test_task_detail_api_returns_404_for_invalid_slug(self):
        self.client.force_authenticate(self.member)

        response = self.client.get(
            f"/api/workspaces/{self.workspace.slug}/projects/{self.project.slug}/tasks/missing-task/"
        )

        self.assertEqual(response.status_code, 404)

    def test_task_patch_updates_only_provided_fields(self):
        self.client.force_authenticate(self.member)

        response = self.client.patch(
            f"/api/workspaces/{self.workspace.slug}/projects/{self.project.slug}/tasks/{self.task.slug}/",
            {"description": "Updated description only"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.description, "Updated description only")
        self.assertEqual(self.task.title, "Ship API")
        self.assertEqual(self.task.status, "todo")

    def test_task_patch_rejects_invalid_field(self):
        self.client.force_authenticate(self.member)

        response = self.client.patch(
            f"/api/workspaces/{self.workspace.slug}/projects/{self.project.slug}/tasks/{self.task.slug}/",
            {"unexpected_field": "value"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("unexpected_field", response.data)

    def test_admin_can_create_workspace_invitation_via_api(self):
        self.client.force_authenticate(self.admin)

        response = self.client.post(
            f"/api/workspaces/{self.workspace.slug}/invitations/",
            {"email": "new-user@example.com", "role": MembershipRole.MEMBER},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["email"], "new-user@example.com")
        self.assertEqual(response.data["workspace"], self.workspace.slug)

    def test_member_cannot_create_workspace_invitation_via_api(self):
        self.client.force_authenticate(self.member)

        response = self.client.post(
            f"/api/workspaces/{self.workspace.slug}/invitations/",
            {"email": "new-user@example.com", "role": MembershipRole.MEMBER},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_invitation_accept_api_rejects_mismatched_email(self):
        invited_user = User.objects.create_user(
            username="wrong-email-user",
            email="wrong-email@example.com",
            password="secret123",
        )
        invitation = create_invitation(
            workspace=self.workspace,
            email="different@example.com",
            role=MembershipRole.MEMBER,
            invited_by=self.owner,
        )
        self.client.force_authenticate(invited_user)

        response = self.client.post(
            f"/api/invitations/{invitation.token}/accept/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["detail"],
            "This invitation is intended for a different email address.",
        )

    def test_invitation_accept_api_creates_membership(self):
        invited_user = User.objects.create_user(
            username="api-invitee",
            email="api-invitee@example.com",
            password="secret123",
        )
        invitation = create_invitation(
            workspace=self.workspace,
            email=invited_user.email,
            role=MembershipRole.ADMIN,
            invited_by=self.owner,
        )
        self.client.force_authenticate(invited_user)

        response = self.client.post(
            f"/api/invitations/{invitation.token}/accept/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["workspace"], self.workspace.slug)
        self.assertEqual(response.data["role"], MembershipRole.ADMIN)
        self.assertTrue(
            Membership.objects.filter(
                workspace=self.workspace,
                user=invited_user,
                role=MembershipRole.ADMIN,
            ).exists()
        )

    def test_member_cannot_archive_project_via_api(self):
        self.client.force_authenticate(self.member)

        response = self.client.post(
            f"/api/workspaces/{self.workspace.slug}/projects/{self.project.slug}/archive/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_admin_can_archive_and_restore_project_via_api(self):
        self.client.force_authenticate(self.admin)

        archive_response = self.client.post(
            f"/api/workspaces/{self.workspace.slug}/projects/{self.project.slug}/archive/",
            {},
            format="json",
        )
        self.assertEqual(archive_response.status_code, 200)
        self.assertTrue(archive_response.data["is_archived"])

        unarchive_response = self.client.post(
            f"/api/workspaces/{self.workspace.slug}/projects/{self.project.slug}/unarchive/",
            {},
            format="json",
        )
        self.assertEqual(unarchive_response.status_code, 200)
        self.assertFalse(unarchive_response.data["is_archived"])

    def test_archived_project_rejects_task_create_via_api(self):
        archive_project(project=self.project, actor=self.owner)
        self.client.force_authenticate(self.member)

        response = self.client.post(
            "/api/tasks/",
            {
                "title": "Blocked task",
                "description": "",
                "priority": "medium",
                "workspace_slug": self.workspace.slug,
                "project_slug": self.project.slug,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["detail"],
            "Tasks cannot be changed in archived projects.",
        )

    def test_archived_project_rejects_task_patch_via_api(self):
        archive_project(project=self.project, actor=self.owner)
        self.client.force_authenticate(self.member)

        response = self.client.patch(
            f"/api/workspaces/{self.workspace.slug}/projects/{self.project.slug}/tasks/{self.task.slug}/",
            {"description": "Blocked update"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_archived_project_rejects_comment_create_via_api(self):
        archive_project(project=self.project, actor=self.owner)
        self.client.force_authenticate(self.member)

        response = self.client.post(
            "/api/comments/",
            {
                "workspace_slug": self.workspace.slug,
                "project_slug": self.project.slug,
                "task_slug": self.task.slug,
                "raw_text": "Blocked comment",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["detail"],
            "Comments cannot be changed in archived projects.",
        )

    def test_archived_project_rejects_comment_delete_via_api(self):
        archive_project(project=self.project, actor=self.owner)
        self.client.force_authenticate(self.member)

        response = self.client.delete(f"/api/comments/{self.comment.id}/")

        self.assertEqual(response.status_code, 403)

    def test_owner_can_update_membership_role_via_api(self):
        membership = self.member.workspace_memberships.get(workspace=self.workspace)
        self.client.force_authenticate(self.owner)

        response = self.client.patch(
            f"/api/workspaces/{self.workspace.slug}/memberships/{membership.id}/",
            {"role": MembershipRole.ADMIN},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["role"], MembershipRole.ADMIN)

    def test_admin_cannot_change_peer_admin_role_via_api(self):
        peer_admin = User.objects.create_user(username="peer-admin", password="secret123")
        peer_membership = Membership.objects.create(
            workspace=self.workspace,
            user=peer_admin,
            role=MembershipRole.ADMIN,
        )
        self.client.force_authenticate(self.admin)

        response = self.client.patch(
            f"/api/workspaces/{self.workspace.slug}/memberships/{peer_membership.id}/",
            {"role": MembershipRole.MEMBER},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_owner_can_remove_member_via_api(self):
        membership = self.member.workspace_memberships.get(workspace=self.workspace)
        self.client.force_authenticate(self.owner)

        response = self.client.delete(
            f"/api/workspaces/{self.workspace.slug}/memberships/{membership.id}/"
        )

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Membership.objects.filter(id=membership.id).exists())

    def test_admin_can_revoke_invitation_via_api(self):
        invitation = create_invitation(
            workspace=self.workspace,
            email="candidate@example.com",
            role=MembershipRole.MEMBER,
            invited_by=self.owner,
        )
        self.client.force_authenticate(self.admin)

        response = self.client.delete(
            f"/api/workspaces/{self.workspace.slug}/invitations/{invitation.id}/"
        )

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Invitation.objects.filter(id=invitation.id).exists())

    def test_owner_can_transfer_ownership_via_api(self):
        target_membership = self.admin.workspace_memberships.get(workspace=self.workspace)
        self.client.force_authenticate(self.owner)

        response = self.client.post(
            f"/api/workspaces/{self.workspace.slug}/transfer-ownership/",
            {"membership_id": target_membership.id},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["owner"], self.admin.username)
        self.workspace.refresh_from_db()
        self.assertEqual(self.workspace.owner, self.admin)

    def test_admin_cannot_transfer_ownership_via_api(self):
        target_membership = self.member.workspace_memberships.get(workspace=self.workspace)
        self.client.force_authenticate(self.admin)

        response = self.client.post(
            f"/api/workspaces/{self.workspace.slug}/transfer-ownership/",
            {"membership_id": target_membership.id},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_admin_can_bulk_update_tasks_via_api(self):
        second_task = create_task(
            project=self.project,
            title="Second bulk task",
            description="",
            priority="medium",
            due_date=None,
            assignee=None,
            created_by=self.member,
        )
        self.client.force_authenticate(self.admin)

        response = self.client.post(
            "/api/tasks/bulk-update/",
            {
                "workspace_slug": self.workspace.slug,
                "project_slug": self.project.slug,
                "task_slugs": [self.task.slug, second_task.slug],
                "assignee_id": self.member.id,
                "status": "done",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["updated_count"], 2)
        self.task.refresh_from_db()
        second_task.refresh_from_db()
        self.assertEqual(self.task.assignee, self.member)
        self.assertEqual(second_task.assignee, self.member)
        self.assertEqual(self.task.status, "done")
        self.assertEqual(second_task.status, "done")

    def test_member_bulk_update_rejects_assignment_via_api(self):
        second_task = create_task(
            project=self.project,
            title="Second bulk task",
            description="Original second",
            priority="medium",
            due_date=None,
            assignee=None,
            created_by=self.member,
        )
        self.client.force_authenticate(self.member)

        response = self.client.post(
            "/api/tasks/bulk-update/",
            {
                "workspace_slug": self.workspace.slug,
                "project_slug": self.project.slug,
                "task_slugs": [self.task.slug, second_task.slug],
                "description": "Blocked bulk update",
                "assignee_id": self.admin.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Only workspace admins can assign tasks.")
        self.task.refresh_from_db()
        second_task.refresh_from_db()
        self.assertEqual(self.task.description, "")
        self.assertEqual(second_task.description, "Original second")

    def test_bulk_update_api_rejects_unknown_task_slug(self):
        self.client.force_authenticate(self.admin)

        response = self.client.post(
            "/api/tasks/bulk-update/",
            {
                "workspace_slug": self.workspace.slug,
                "project_slug": self.project.slug,
                "task_slugs": [self.task.slug, "missing-task"],
                "status": "done",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("task_slugs", response.data)


class TaskTagAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(username="api_tag_owner", password="password123")
        self.admin = User.objects.create_user(username="api_tag_admin", password="password123")
        self.member = User.objects.create_user(username="api_tag_member", password="password123")
        self.outsider = User.objects.create_user(
            username="api_tag_outsider", password="password123"
        )

        self.workspace = create_workspace(owner=self.owner, name="Tag API WS")
        Membership.objects.create(
            workspace=self.workspace, user=self.admin, role=MembershipRole.ADMIN
        )
        Membership.objects.create(
            workspace=self.workspace, user=self.member, role=MembershipRole.MEMBER
        )

    def test_owner_can_list_and_create_tag(self):
        self.client.force_authenticate(self.owner)
        url = f"/api/workspaces/{self.workspace.slug}/tags/"

        post_res = self.client.post(url, {"name": "Security", "color": "#ff0000"}, format="json")
        self.assertEqual(post_res.status_code, 201)
        self.assertEqual(post_res.data["name"], "Security")
        self.assertEqual(post_res.data["slug"], "security")
        self.assertEqual(post_res.data["color"], "#ff0000")

        get_res = self.client.get(url)
        self.assertEqual(get_res.status_code, 200)
        self.assertEqual(get_res.data["count"], 1)
        self.assertEqual(len(get_res.data["results"]), 1)

    def test_member_can_list_but_cannot_create_tag(self):
        create_task_tag(workspace=self.workspace, name="DevOps", actor=self.owner)
        self.client.force_authenticate(self.member)
        url = f"/api/workspaces/{self.workspace.slug}/tags/"

        get_res = self.client.get(url)
        self.assertEqual(get_res.status_code, 200)
        self.assertEqual(get_res.data["count"], 1)
        self.assertEqual(len(get_res.data["results"]), 1)

        post_res = self.client.post(url, {"name": "QA", "color": "#123456"}, format="json")
        self.assertEqual(post_res.status_code, 403)

    def test_tag_detail_update_and_delete(self):
        tag = create_task_tag(workspace=self.workspace, name="Backend", actor=self.owner)
        self.client.force_authenticate(self.admin)
        url = f"/api/workspaces/{self.workspace.slug}/tags/{tag.id}/"

        patch_res = self.client.patch(
            url, {"name": "Core Backend", "color": "#0000ff"}, format="json"
        )
        self.assertEqual(patch_res.status_code, 200)
        self.assertEqual(patch_res.data["name"], "Core Backend")
        self.assertEqual(patch_res.data["color"], "#0000ff")

        del_res = self.client.delete(url)
        self.assertEqual(del_res.status_code, 204)
        self.assertEqual(TaskTag.objects.filter(id=tag.id).count(), 0)


class TaskChecklistAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(username="api_cl_owner", password="password123")
        self.member = User.objects.create_user(username="api_cl_member", password="password123")
        self.outsider = User.objects.create_user(
            username="api_cl_outsider", password="password123"
        )

        self.workspace = create_workspace(owner=self.owner, name="CL API WS")
        Membership.objects.create(
            workspace=self.workspace, user=self.member, role=MembershipRole.MEMBER
        )
        self.project = create_project(
            workspace=self.workspace, name="CL Project", description="", created_by=self.owner
        )
        self.task = create_task(
            project=self.project,
            title="CL Task",
            description="",
            priority="medium",
            due_date=None,
            assignee=None,
            created_by=self.member,
        )

    def test_checklist_crud_and_toggle(self):
        self.client.force_authenticate(self.member)
        ws_slug = self.workspace.slug
        p_slug = self.project.slug
        t_slug = self.task.slug
        base_url = f"/api/workspaces/{ws_slug}/projects/{p_slug}/tasks/{t_slug}/checklist/"

        # Create
        create_res = self.client.post(base_url, {"text": "Step 1"}, format="json")
        self.assertEqual(create_res.status_code, 201)
        item_id = create_res.data["id"]
        self.assertEqual(create_res.data["text"], "Step 1")
        self.assertFalse(create_res.data["is_completed"])

        # List
        list_res = self.client.get(base_url)
        self.assertEqual(list_res.status_code, 200)
        self.assertEqual(list_res.data["count"], 1)
        self.assertEqual(len(list_res.data["results"]), 1)

        # Toggle
        toggle_res = self.client.post(f"{base_url}{item_id}/toggle/")
        self.assertEqual(toggle_res.status_code, 200)
        self.assertTrue(toggle_res.data["is_completed"])

        # Update
        patch_res = self.client.patch(
            f"{base_url}{item_id}/", {"text": "Step 1 revised"}, format="json"
        )
        self.assertEqual(patch_res.status_code, 200)
        self.assertEqual(patch_res.data["text"], "Step 1 revised")

        # Delete
        del_res = self.client.delete(f"{base_url}{item_id}/")
        self.assertEqual(del_res.status_code, 204)
        self.assertEqual(TaskChecklistItem.objects.filter(id=item_id).count(), 0)

    def test_checklist_create_with_is_completed(self):
        self.client.force_authenticate(self.member)
        url = (
            f"/api/workspaces/{self.workspace.slug}/projects/{self.project.slug}/"
            f"tasks/{self.task.slug}/checklist/"
        )
        res = self.client.post(
            url, {"text": "Step pre-completed", "is_completed": True}, format="json"
        )
        self.assertEqual(res.status_code, 201)
        self.assertTrue(res.data["is_completed"])

    def test_checklist_reorder_api(self):
        item1 = add_checklist_item(task=self.task, text="Item A", actor=self.member)
        item2 = add_checklist_item(task=self.task, text="Item B", actor=self.member)
        self.client.force_authenticate(self.member)
        url = (
            f"/api/workspaces/{self.workspace.slug}/projects/{self.project.slug}/"
            f"tasks/{self.task.slug}/checklist/reorder/"
        )

        response = self.client.post(url, {"item_ids": [item2.id, item1.id]}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([i["id"] for i in response.data], [item2.id, item1.id])


class TaskLifecycleAndDeletionAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(username="api_life_owner", password="password123")
        self.member = User.objects.create_user(username="api_life_member", password="password123")
        self.other_member = User.objects.create_user(
            username="api_life_other", password="password123"
        )

        self.workspace = create_workspace(owner=self.owner, name="Life API WS")
        Membership.objects.create(
            workspace=self.workspace, user=self.member, role=MembershipRole.MEMBER
        )
        Membership.objects.create(
            workspace=self.workspace, user=self.other_member, role=MembershipRole.MEMBER
        )
        self.project = create_project(
            workspace=self.workspace, name="Life Project", description="", created_by=self.owner
        )
        self.tag = create_task_tag(workspace=self.workspace, name="Frontend", actor=self.owner)
        self.task = create_task(
            project=self.project,
            title="Life Task",
            description="",
            priority="medium",
            due_date=None,
            assignee=None,
            created_by=self.member,
        )

    def test_task_representation_includes_tags_checklist_and_archived(self):
        self.client.force_authenticate(self.member)
        url = (
            f"/api/workspaces/{self.workspace.slug}/projects/{self.project.slug}/"
            f"tasks/{self.task.slug}/"
        )

        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertIn("tags", res.data)
        self.assertIn("checklist_items", res.data)
        self.assertIn("is_archived", res.data)
        self.assertFalse(res.data["is_archived"])

    def test_archive_and_restore_api(self):
        self.client.force_authenticate(self.member)
        ws_slug = self.workspace.slug
        p_slug = self.project.slug
        t_slug = self.task.slug
        archive_url = f"/api/workspaces/{ws_slug}/projects/{p_slug}/tasks/{t_slug}/archive/"
        restore_url = f"/api/workspaces/{ws_slug}/projects/{p_slug}/tasks/{t_slug}/restore/"

        arc_res = self.client.post(archive_url)
        self.assertEqual(arc_res.status_code, 200)
        self.assertTrue(arc_res.data["is_archived"])

        res_res = self.client.post(restore_url)
        self.assertEqual(res_res.status_code, 200)
        self.assertFalse(res_res.data["is_archived"])

    def test_task_delete_api(self):
        task_to_del = create_task(
            project=self.project,
            title="Task for API Delete",
            description="",
            priority="low",
            due_date=None,
            assignee=None,
            created_by=self.member,
        )
        url = (
            f"/api/workspaces/{self.workspace.slug}/projects/{self.project.slug}/"
            f"tasks/{task_to_del.slug}/"
        )

        # Other member cannot delete
        self.client.force_authenticate(self.other_member)
        del_res_other = self.client.delete(url)
        self.assertEqual(del_res_other.status_code, 403)

        # Creator can delete
        self.client.force_authenticate(self.member)
        del_res = self.client.delete(url)
        self.assertEqual(del_res.status_code, 204)
        self.assertEqual(Task.objects.filter(id=task_to_del.id).count(), 0)

    def test_create_and_update_task_with_tag_ids(self):
        self.client.force_authenticate(self.member)
        url = "/api/tasks/"
        res = self.client.post(
            url,
            {
                "workspace_slug": self.workspace.slug,
                "project_slug": self.project.slug,
                "title": "Tagged Task API",
                "priority": "high",
                "tag_ids": [self.tag.id],
            },
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        created_slug = res.data["slug"]
        created_task = Task.objects.get(project=self.project, slug=created_slug)
        self.assertIn(self.tag, created_task.tags.all())

    def test_task_patch_atomic_rollback_on_invalid_tag_ids(self):
        self.client.force_authenticate(self.member)
        url = (
            f"/api/workspaces/{self.workspace.slug}/projects/{self.project.slug}/"
            f"tasks/{self.task.slug}/"
        )
        original_title = self.task.title
        original_desc = self.task.description

        response = self.client.patch(
            url,
            {
                "title": "Should Not Persist",
                "description": "Neither should this",
                "tag_ids": [999999],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("detail", response.data)
        self.task.refresh_from_db()
        self.assertEqual(self.task.title, original_title)
        self.assertEqual(self.task.description, original_desc)

