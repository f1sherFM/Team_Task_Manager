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
    revoke_invitation,
    transfer_workspace_ownership,
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
            remove_membership(membership=owner_membership, actor=self.owner)

    def test_owner_role_cannot_be_assigned_after_workspace_creation(self):
        workspace = create_workspace(owner=self.owner, name="Core Team")
        membership = Membership.objects.create(
            workspace=workspace,
            user=self.admin,
            role=MembershipRole.ADMIN,
        )

        with self.assertRaises(DomainError):
            change_membership_role(
                membership=membership,
                role=MembershipRole.OWNER,
                actor=self.owner,
            )

    def test_admin_cannot_change_another_admin_role(self):
        workspace = create_workspace(owner=self.owner, name="Core Team")
        peer_admin = User.objects.create_user(
            username="peer-admin",
            email="peer-admin@example.com",
            password="secret123",
        )
        Membership.objects.create(workspace=workspace, user=self.admin, role=MembershipRole.ADMIN)
        target_membership = Membership.objects.create(
            workspace=workspace,
            user=peer_admin,
            role=MembershipRole.ADMIN,
        )

        with self.assertRaises(DomainError):
            change_membership_role(
                membership=target_membership,
                role=MembershipRole.MEMBER,
                actor=self.admin,
            )

    def test_owner_can_transfer_workspace_ownership(self):
        workspace = create_workspace(owner=self.owner, name="Core Team")
        target_membership = Membership.objects.create(
            workspace=workspace,
            user=self.admin,
            role=MembershipRole.ADMIN,
        )

        transfer_workspace_ownership(
            workspace=workspace,
            new_owner_membership=target_membership,
            actor=self.owner,
        )

        workspace.refresh_from_db()
        target_membership.refresh_from_db()
        previous_owner_membership = Membership.objects.get(workspace=workspace, user=self.owner)
        self.assertEqual(workspace.owner, self.admin)
        self.assertEqual(target_membership.role, MembershipRole.OWNER)
        self.assertEqual(previous_owner_membership.role, MembershipRole.ADMIN)

    def test_admin_cannot_transfer_workspace_ownership(self):
        workspace = create_workspace(owner=self.owner, name="Core Team")
        Membership.objects.create(workspace=workspace, user=self.admin, role=MembershipRole.ADMIN)
        target_membership = Membership.objects.create(
            workspace=workspace,
            user=self.invited_user,
            role=MembershipRole.MEMBER,
        )

        with self.assertRaises(DomainError):
            transfer_workspace_ownership(
                workspace=workspace,
                new_owner_membership=target_membership,
                actor=self.admin,
            )

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

    def test_revoke_invitation_deletes_pending_invitation(self):
        workspace = create_workspace(owner=self.owner, name="Core Team")
        invitation = create_invitation(
            workspace=workspace,
            email=self.invited_user.email,
            role=MembershipRole.MEMBER,
            invited_by=self.owner,
        )

        revoke_invitation(invitation=invitation, actor=self.owner)

        self.assertFalse(Invitation.objects.filter(id=invitation.id).exists())

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

    def test_workspace_members_view_can_update_membership_role(self):
        workspace = create_workspace(owner=self.owner, name="Core Team")
        membership = Membership.objects.create(
            workspace=workspace,
            user=self.admin,
            role=MembershipRole.MEMBER,
        )
        self.client.login(username="owner", password="secret123")

        response = self.client.post(
            f"/workspaces/{workspace.slug}/members/{membership.id}/role/",
            {"role": MembershipRole.ADMIN},
        )

        self.assertEqual(response.status_code, 302)
        membership.refresh_from_db()
        self.assertEqual(membership.role, MembershipRole.ADMIN)

    def test_workspace_members_view_can_revoke_invitation(self):
        workspace = create_workspace(owner=self.owner, name="Core Team")
        invitation = create_invitation(
            workspace=workspace,
            email="new-member@example.com",
            role=MembershipRole.MEMBER,
            invited_by=self.owner,
        )
        self.client.login(username="owner", password="secret123")

        response = self.client.post(
            f"/workspaces/{workspace.slug}/invitations/{invitation.id}/revoke/"
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Invitation.objects.filter(id=invitation.id).exists())

    def test_workspace_members_view_can_transfer_ownership(self):
        workspace = create_workspace(owner=self.owner, name="Core Team")
        membership = Membership.objects.create(
            workspace=workspace,
            user=self.admin,
            role=MembershipRole.ADMIN,
        )
        self.client.login(username="owner", password="secret123")

        response = self.client.post(
            f"/workspaces/{workspace.slug}/transfer-ownership/",
            {"membership_id": membership.id},
        )

        self.assertEqual(response.status_code, 302)
        workspace.refresh_from_db()
        membership.refresh_from_db()
        self.assertEqual(workspace.owner, self.admin)
        self.assertEqual(membership.role, MembershipRole.OWNER)
