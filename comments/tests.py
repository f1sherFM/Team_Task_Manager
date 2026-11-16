from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from comments.models import Comment
from comments.services import add_comment, soft_delete_comment
from core.exceptions import DomainError
from projects.services import archive_project, create_project
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
        Membership.objects.create(
            workspace=self.workspace,
            user=self.author,
            role=MembershipRole.MEMBER,
        )
        Membership.objects.create(
            workspace=self.workspace,
            user=self.member,
            role=MembershipRole.MEMBER,
        )
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

    def test_cannot_add_comment_in_archived_project(self):
        archive_project(project=self.project, actor=self.owner)

        with self.assertRaises(DomainError):
            add_comment(task=self.task, author=self.author, text="Blocked note")

    def test_cannot_delete_comment_in_archived_project(self):
        comment = add_comment(task=self.task, author=self.author, text="Initial note")
        archive_project(project=self.project, actor=self.owner)

        with self.assertRaises(DomainError):
            soft_delete_comment(comment=comment, actor=self.author)


class CommentViewTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="secret123")
        self.author = User.objects.create_user(username="author", password="secret123")
        self.member = User.objects.create_user(username="member", password="secret123")
        self.outsider = User.objects.create_user(username="outsider", password="secret123")

        self.workspace = create_workspace(owner=self.owner, name="Engineering")
        Membership.objects.create(
            workspace=self.workspace,
            user=self.author,
            role=MembershipRole.MEMBER,
        )
        Membership.objects.create(
            workspace=self.workspace,
            user=self.member,
            role=MembershipRole.MEMBER,
        )
        self.project = create_project(
            workspace=self.workspace,
            name="Platform",
            description="Core platform",
            created_by=self.owner,
        )
        self.task = create_task(
            project=self.project,
            title="Ship comments",
            description="Details",
            priority="medium",
            due_date=None,
            assignee=None,
            created_by=self.author,
        )
        self.create_url = reverse(
            "comment-create",
            kwargs={
                "workspace_slug": self.workspace.slug,
                "project_slug": self.project.slug,
                "task_slug": self.task.slug,
            },
        )

    def test_create_comment_standard_success(self):
        self.client.force_login(self.author)
        response = self.client.post(self.create_url, {"text": "A standard comment."})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Comment.objects.filter(task=self.task, text="A standard comment.").exists())

    def test_create_comment_htmx_success(self):
        self.client.force_login(self.author)
        response = self.client.post(
            self.create_url,
            {"text": "An HTMX comment."},
            headers={"HX-Request": "true"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "An HTMX comment.")
        self.assertContains(response, 'hx-swap-oob="beforeend:#comments-list"')
        self.assertContains(response, 'id="comments-count"')
        self.assertContains(response, 'id="no-comments-message" hx-swap-oob="delete"')
        self.assertTrue(Comment.objects.filter(task=self.task, text="An HTMX comment.").exists())

    def test_create_comment_htmx_validation_error(self):
        self.client.force_login(self.author)
        response = self.client.post(
            self.create_url,
            {"text": ""},
            headers={"HX-Request": "true"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required")
        self.assertContains(response, 'id="comment-form-container"')

    def test_create_comment_outsider_forbidden(self):
        self.client.force_login(self.outsider)
        response = self.client.post(self.create_url, {"text": "Should not work."})
        self.assertEqual(response.status_code, 404)

    def test_create_comment_archived_project_blocked(self):
        archive_project(project=self.project, actor=self.owner)
        self.client.force_login(self.author)
        response = self.client.post(
            self.create_url,
            {"text": "Should fail."},
            headers={"HX-Request": "true"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Comments cannot be changed in archived projects.")

    def test_delete_comment_standard_success(self):
        comment = add_comment(task=self.task, author=self.author, text="To be deleted.")
        delete_url = reverse("comment-delete", kwargs={"comment_id": comment.id})
        self.client.force_login(self.author)
        response = self.client.post(delete_url)
        self.assertEqual(response.status_code, 302)
        comment.refresh_from_db()
        self.assertTrue(comment.is_deleted)
        self.assertEqual(comment.text, "")

    def test_delete_comment_htmx_success(self):
        comment = add_comment(task=self.task, author=self.author, text="To be deleted via HTMX.")
        delete_url = reverse("comment-delete", kwargs={"comment_id": comment.id})
        self.client.force_login(self.author)
        response = self.client.post(delete_url, headers={"HX-Request": "true"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "[deleted]")
        self.assertNotContains(response, "To be deleted via HTMX.")
        self.assertNotContains(response, "btn-outline-danger")
        comment.refresh_from_db()
        self.assertTrue(comment.is_deleted)

    def test_delete_comment_htmx_unauthorized_returns_403(self):
        comment = add_comment(task=self.task, author=self.author, text="Author only.")
        delete_url = reverse("comment-delete", kwargs={"comment_id": comment.id})
        self.client.force_login(self.member)
        response = self.client.post(delete_url, headers={"HX-Request": "true"})
        self.assertEqual(response.status_code, 403)
        self.assertNotIn("HX-Redirect", response.headers)
        comment.refresh_from_db()
        self.assertFalse(comment.is_deleted)

    def test_delete_comment_htmx_admin_allowed(self):
        comment = add_comment(task=self.task, author=self.author, text="Admin can delete.")
        delete_url = reverse("comment-delete", kwargs={"comment_id": comment.id})
        self.client.force_login(self.owner)
        response = self.client.post(delete_url, headers={"HX-Request": "true"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "[deleted]")
        comment.refresh_from_db()
        self.assertTrue(comment.is_deleted)
