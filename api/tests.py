from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from activity.models import ActivityLog
from activity.services import log_activity
from comments.services import add_comment
from projects.models import Project
from projects.services import create_project
from tasks.models import Task
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

        response = self.client.get("/api/projects/", {"ordering": "-created_at", "workspace": self.workspace.slug})

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

        response = self.client.get("/api/tasks/", {"ordering": "-created_at", "project": self.project.slug})

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
