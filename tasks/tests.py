from django.test import TestCase
from django.contrib.auth import get_user_model

from core.exceptions import DomainError
from projects.services import create_project
from tasks.models import TaskStatus
from tasks.services import assign_task, change_task_status, create_task
from workspaces.models import Membership, MembershipRole
from workspaces.services import create_workspace


User = get_user_model()


class TaskServiceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="secret123")
        self.admin = User.objects.create_user(username="admin", password="secret123")
        self.member = User.objects.create_user(username="member", password="secret123")
        self.other = User.objects.create_user(username="other", password="secret123")

        self.workspace = create_workspace(owner=self.owner, name="Engineering")
        Membership.objects.create(workspace=self.workspace, user=self.admin, role=MembershipRole.ADMIN)
        Membership.objects.create(workspace=self.workspace, user=self.member, role=MembershipRole.MEMBER)
        Membership.objects.create(workspace=self.workspace, user=self.other, role=MembershipRole.MEMBER)
        self.project = create_project(
            workspace=self.workspace,
            name="API",
            description="Core API",
            created_by=self.owner,
        )

    def test_workspace_member_can_create_task(self):
        task = create_task(
            project=self.project,
            title="Implement endpoint",
            description="",
            priority="medium",
            due_date=None,
            assignee=None,
            created_by=self.member,
        )

        self.assertEqual(task.created_by, self.member)

    def test_non_admin_cannot_assign_task(self):
        task = create_task(
            project=self.project,
            title="Implement endpoint",
            description="",
            priority="medium",
            due_date=None,
            assignee=None,
            created_by=self.member,
        )

        with self.assertRaises(DomainError):
            assign_task(task=task, assignee=self.other, actor=self.member)

    def test_assignee_can_change_status(self):
        task = create_task(
            project=self.project,
            title="Implement endpoint",
            description="",
            priority="medium",
            due_date=None,
            assignee=None,
            created_by=self.member,
        )
        task = assign_task(task=task, assignee=self.member, actor=self.admin)
        updated_task = change_task_status(task=task, status=TaskStatus.DONE, actor=self.member)

        self.assertEqual(updated_task.status, TaskStatus.DONE)

    def test_non_assignee_member_cannot_change_status(self):
        task = create_task(
            project=self.project,
            title="Implement endpoint",
            description="",
            priority="medium",
            due_date=None,
            assignee=None,
            created_by=self.member,
        )
        task = assign_task(task=task, assignee=self.member, actor=self.admin)

        with self.assertRaises(DomainError):
            change_task_status(task=task, status=TaskStatus.DONE, actor=self.other)
