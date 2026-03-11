from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from comments.services import add_comment
from projects.services import create_project
from tasks.services import assign_task, create_task
from workspaces.models import Membership, MembershipRole
from workspaces.services import create_workspace


User = get_user_model()


class ApiPermissionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(username="owner", password="secret123")
        self.admin = User.objects.create_user(username="admin", password="secret123")
        self.member = User.objects.create_user(username="member", password="secret123")
        self.outsider = User.objects.create_user(username="outsider", password="secret123")

        self.workspace = create_workspace(owner=self.owner, name="Engineering")
        Membership.objects.create(workspace=self.workspace, user=self.admin, role=MembershipRole.ADMIN)
        Membership.objects.create(workspace=self.workspace, user=self.member, role=MembershipRole.MEMBER)
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
