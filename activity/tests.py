from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from activity.selectors import filter_activity_logs, get_user_activity, get_workspace_activity
from activity.services import log_activity
from workspaces.services import create_workspace

User = get_user_model()


class ActivityLogModelAndServiceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="act_owner", password="password123")
        self.workspace = create_workspace(owner=self.owner, name="Act Workspace")

    def test_activity_log_creation_and_str(self):
        log = log_activity(
            workspace=self.workspace,
            actor=self.owner,
            action="task_created",
            target_type="task",
            target_id="101",
            metadata={"title": "Test Task"},
        )
        self.assertEqual(str(log), "task_created on task:101")
        self.assertEqual(log.metadata, {"title": "Test Task"})
        self.assertEqual(log.workspace, self.workspace)
        self.assertEqual(log.actor, self.owner)

    def test_activity_log_is_append_only(self):
        log = log_activity(
            workspace=self.workspace,
            actor=self.owner,
            action="task_created",
            target_type="task",
            target_id="102",
        )
        log.action = "tampered_action"
        with self.assertRaises(ValueError) as ctx:
            log.save()
        self.assertIn("ActivityLog is append-only", str(ctx.exception))

    def test_log_activity_with_none_actor(self):
        log = log_activity(
            workspace=self.workspace,
            actor=None,
            action="system_event",
            target_type="workspace",
            target_id=str(self.workspace.id),
        )
        self.assertIsNone(log.actor)
        self.assertEqual(log.action, "system_event")


class ActivityLogSelectorTests(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username="user1", password="password123")
        self.user2 = User.objects.create_user(username="user2", password="password123")
        self.ws1 = create_workspace(owner=self.user1, name="Workspace 1")
        self.ws2 = create_workspace(owner=self.user2, name="Workspace 2")

        self.log1 = log_activity(
            workspace=self.ws1,
            actor=self.user1,
            action="task_created",
            target_type="task",
            target_id="1",
        )
        self.log2 = log_activity(
            workspace=self.ws1,
            actor=self.user1,
            action="comment_added",
            target_type="comment",
            target_id="2",
        )
        self.log3 = log_activity(
            workspace=self.ws2,
            actor=self.user2,
            action="task_created",
            target_type="task",
            target_id="3",
        )

    def test_get_workspace_activity(self):
        ws1_logs = list(get_workspace_activity(self.ws1))
        self.assertEqual(len(ws1_logs), 2)
        self.assertIn(self.log1, ws1_logs)
        self.assertIn(self.log2, ws1_logs)
        self.assertNotIn(self.log3, ws1_logs)

    def test_get_user_activity_isolation(self):
        user1_logs = list(get_user_activity(self.user1))
        self.assertEqual(len(user1_logs), 2)
        self.assertNotIn(self.log3, user1_logs)

        user2_logs = list(get_user_activity(self.user2))
        self.assertEqual(len(user2_logs), 1)
        self.assertEqual(user2_logs[0], self.log3)

    def test_filter_activity_logs(self):
        qs = get_workspace_activity(self.ws1)
        filtered_by_action = filter_activity_logs(qs, action="comment_added")
        self.assertEqual(list(filtered_by_action), [self.log2])

        filtered_by_target = filter_activity_logs(qs, target_type="task")
        self.assertEqual(list(filtered_by_target), [self.log1])


class WorkspaceActivityViewTests(TestCase):
    def setUp(self):
        self.member = User.objects.create_user(username="member_user", password="password123")
        self.outsider = User.objects.create_user(username="outsider_user", password="password123")
        self.workspace = create_workspace(owner=self.member, name="Visible WS")
        self.log = log_activity(
            workspace=self.workspace,
            actor=self.member,
            action="task_created",
            target_type="task",
            target_id="10",
        )

    def test_unauthenticated_redirects_login(self):
        url = reverse("workspace-activity", kwargs={"slug": self.workspace.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_non_member_gets_404(self):
        self.client.force_login(self.outsider)
        url = reverse("workspace-activity", kwargs={"slug": self.workspace.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_member_can_view_activity(self):
        self.client.force_login(self.member)
        url = reverse("workspace-activity", kwargs={"slug": self.workspace.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "activity/workspace_activity.html")
        self.assertContains(response, "Task Created")

    def test_activity_pagination(self):
        for i in range(30):
            log_activity(
                workspace=self.workspace,
                actor=self.member,
                action="task_created",
                target_type="task",
                target_id=str(100 + i),
            )
        self.client.force_login(self.member)
        url = reverse("workspace-activity", kwargs={"slug": self.workspace.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["is_paginated"])
        self.assertEqual(len(response.context["activity_logs"]), 25)

        response_p2 = self.client.get(url + "?page=2")
        self.assertEqual(response_p2.status_code, 200)
        self.assertEqual(len(response_p2.context["activity_logs"]), 6)
