from django.test import TestCase
from django.contrib.auth import get_user_model

from core.exceptions import DomainError
from comments.services import add_comment, soft_delete_comment
from projects.services import create_project
from tasks.services import create_task
from workspaces.models import Membership, MembershipRole
from workspaces.services import create_workspace


User = get_user_model()


class CommentServiceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="secret123")
        self.author = User.objects.create_user(username="author", password="secret123")
        self.member = User.objects.create_user(username="member", password="secret123")
        self.workspace = create_workspace(owner=self.owner, name="Engineering")
        Membership.objects.create(workspace=self.workspace, user=self.author, role=MembershipRole.MEMBER)
        Membership.objects.create(workspace=self.workspace, user=self.member, role=MembershipRole.MEMBER)
        self.project = create_project(
            workspace=self.workspace,
            name="Platform",
            description="Core platform",
            created_by=self.owner,
        )
        self.task = create_task(
            project=self.project,
            title="Ship comments",
            description="",
            priority="medium",
            due_date=None,
            assignee=None,
            created_by=self.author,
        )

    def test_soft_delete_marks_comment_deleted_and_erases_text(self):
        comment = add_comment(task=self.task, author=self.author, text="Initial note")

        deleted_comment = soft_delete_comment(comment=comment, actor=self.author)

        self.assertTrue(deleted_comment.is_deleted)
        self.assertEqual(deleted_comment.text, "")

    def test_non_author_member_cannot_delete_comment(self):
        comment = add_comment(task=self.task, author=self.author, text="Initial note")

        with self.assertRaises(DomainError):
            soft_delete_comment(comment=comment, actor=self.member)
