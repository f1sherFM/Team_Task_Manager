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
from tasks.models import Task
from tasks.services import assign_task, create_task
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
