from django.contrib.auth import get_user_model
from django.test import TestCase

from core.exceptions import DomainError
from projects.services import archive_project, create_project, unarchive_project
from workspaces.models import Membership, MembershipRole
from workspaces.services import create_workspace

User = get_user_model()


class ProjectServiceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="secret123")
        self.admin = User.objects.create_user(username="admin", password="secret123")
        self.member = User.objects.create_user(username="member", password="secret123")
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
            name="Platform",
            description="Core platform",
            created_by=self.owner,
        )

    def test_workspace_member_without_admin_role_cannot_create_project(self):
        with self.assertRaises(DomainError):
            create_project(
                workspace=self.workspace,
                name="Forbidden project",
                description="No access",
                created_by=self.member,
            )

    def test_member_cannot_archive_project(self):
        with self.assertRaises(DomainError):
            archive_project(project=self.project, actor=self.member)

    def test_admin_can_archive_and_restore_project(self):
        archived_project = archive_project(project=self.project, actor=self.admin)
        self.assertTrue(archived_project.is_archived)

        restored_project = unarchive_project(project=archived_project, actor=self.admin)
        self.assertFalse(restored_project.is_archived)

    def test_project_archive_view_archives_project(self):
        self.client.login(username="owner", password="secret123")

        response = self.client.post(
            f"/workspaces/{self.workspace.slug}/projects/{self.project.slug}/archive/"
        )

        self.assertEqual(response.status_code, 302)
        self.project.refresh_from_db()
        self.assertTrue(self.project.is_archived)
