from django.contrib.auth import get_user_model
from django.test import TestCase

from core.exceptions import DomainError
from projects.services import create_project
from workspaces.models import Membership, MembershipRole
from workspaces.services import create_workspace


User = get_user_model()


class ProjectServiceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="secret123")
        self.member = User.objects.create_user(username="member", password="secret123")
        self.workspace = create_workspace(owner=self.owner, name="Engineering")
        Membership.objects.create(
            workspace=self.workspace,
            user=self.member,
            role=MembershipRole.MEMBER,
        )

    def test_workspace_member_without_admin_role_cannot_create_project(self):
        with self.assertRaises(DomainError):
            create_project(
                workspace=self.workspace,
                name="Forbidden project",
                description="No access",
                created_by=self.member,
            )
