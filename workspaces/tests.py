from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core.exceptions import DomainError
from workspaces.models import Invitation, Membership, MembershipRole
from workspaces.services import (
    accept_invitation,
    change_membership_role,
    create_invitation,
    create_workspace,
    remove_membership,
)

User = get_user_model()


class WorkspaceServiceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="secret123",
        )
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="secret123",
        )
        self.invited_user = User.objects.create_user(
            username="invitee",
            email="invitee@example.com",
            password="secret123",
        )

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

    def test_owner_role_cannot_be_assigned_after_workspace_creation(self):
        workspace = create_workspace(owner=self.owner, name="Core Team")
        membership = Membership.objects.create(
            workspace=workspace,
            user=self.admin,
            role=MembershipRole.ADMIN,
        )

        with self.assertRaises(DomainError):
            change_membership_role(membership=membership, role=MembershipRole.OWNER)

    def test_create_invitation_rejects_existing_member(self):
        workspace = create_workspace(owner=self.owner, name="Core Team")

        with self.assertRaises(DomainError):
            create_invitation(
                workspace=workspace,
                email=self.owner.email,
                role=MembershipRole.MEMBER,
                invited_by=self.owner,
            )

    def test_create_invitation_rejects_duplicate_active_invitation(self):
        workspace = create_workspace(owner=self.owner, name="Core Team")
        create_invitation(
            workspace=workspace,
            email=self.invited_user.email,
            role=MembershipRole.MEMBER,
            invited_by=self.owner,
        )

        with self.assertRaises(DomainError):
            create_invitation(
                workspace=workspace,
                email=self.invited_user.email,
                role=MembershipRole.ADMIN,
                invited_by=self.owner,
            )

    def test_accept_invitation_creates_membership_and_sets_accepted_at(self):
        workspace = create_workspace(owner=self.owner, name="Core Team")
        invitation = create_invitation(
            workspace=workspace,
            email=self.invited_user.email,
            role=MembershipRole.ADMIN,
            invited_by=self.owner,
        )

        membership = accept_invitation(invitation=invitation, user=self.invited_user)
        invitation.refresh_from_db()

        self.assertEqual(membership.workspace, workspace)
        self.assertEqual(membership.user, self.invited_user)
        self.assertEqual(membership.role, MembershipRole.ADMIN)
        self.assertIsNotNone(invitation.accepted_at)

    def test_accept_invitation_rejects_expired_invitation(self):
        workspace = create_workspace(owner=self.owner, name="Core Team")
        invitation = create_invitation(
            workspace=workspace,
            email=self.invited_user.email,
            role=MembershipRole.MEMBER,
            invited_by=self.owner,
        )
        Invitation.objects.filter(id=invitation.id).update(
            expires_at=timezone.now() - timezone.timedelta(minutes=1)
        )
        invitation.refresh_from_db()

        with self.assertRaises(DomainError):
            accept_invitation(invitation=invitation, user=self.invited_user)

    def test_accept_invitation_rejects_mismatched_email(self):
        workspace = create_workspace(owner=self.owner, name="Core Team")
        invitation = create_invitation(
            workspace=workspace,
            email="other@example.com",
            role=MembershipRole.MEMBER,
            invited_by=self.owner,
        )

        with self.assertRaises(DomainError):
            accept_invitation(invitation=invitation, user=self.invited_user)

    def test_workspace_members_view_creates_invitation_for_admin(self):
        workspace = create_workspace(owner=self.owner, name="Core Team")
        self.client.login(username="owner", password="secret123")

        response = self.client.post(
            f"/workspaces/{workspace.slug}/members/",
            {"email": "new-member@example.com", "role": MembershipRole.MEMBER},
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Invitation.objects.filter(
                workspace=workspace,
                email="new-member@example.com",
                role=MembershipRole.MEMBER,
            ).exists()
        )

    def test_invitation_accept_view_creates_membership(self):
        workspace = create_workspace(owner=self.owner, name="Core Team")
        invitation = create_invitation(
            workspace=workspace,
            email=self.invited_user.email,
            role=MembershipRole.ADMIN,
            invited_by=self.owner,
        )
        self.client.login(username="invitee", password="secret123")

        response = self.client.post(f"/invitations/{invitation.token}/accept/")

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Membership.objects.filter(
                workspace=workspace,
                user=self.invited_user,
                role=MembershipRole.ADMIN,
            ).exists()
        )
