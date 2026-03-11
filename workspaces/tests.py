from django.test import TestCase
from django.contrib.auth import get_user_model

from core.exceptions import DomainError
from workspaces.models import Membership, MembershipRole
from workspaces.services import create_workspace, remove_membership


User = get_user_model()


class WorkspaceServiceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="secret123")

    def test_create_workspace_creates_owner_membership(self):
        workspace = create_workspace(owner=self.owner, name="Core Team")

        membership = Membership.objects.get(workspace=workspace, user=self.owner)
        self.assertEqual(workspace.owner, self.owner)
        self.assertEqual(membership.role, MembershipRole.OWNER)

    def test_owner_membership_cannot_be_removed(self):
        workspace = create_workspace(owner=self.owner, name="Core Team")
        owner_membership = Membership.objects.get(workspace=workspace, user=self.owner)

        with self.assertRaises(DomainError):
            remove_membership(membership=owner_membership)
