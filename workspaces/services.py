from django.db import transaction
from django.utils import timezone

from core.exceptions import DomainError
from core.permissions import (
    can_delete_workspace,
    can_manage_invitations,
    can_manage_membership,
    can_transfer_workspace_ownership,
    has_membership_role,
)
from core.slugs import create_with_unique_slug
from workspaces.models import Invitation, Membership, MembershipRole, Workspace


@transaction.atomic
def create_workspace(*, owner, name: str) -> Workspace:
    workspace = create_with_unique_slug(
        model=Workspace,
        value=name,
        create_kwargs={"name": name, "owner": owner},
    )
    Membership.objects.create(workspace=workspace, user=owner, role=MembershipRole.OWNER)
    return workspace


@transaction.atomic
def create_invitation(*, workspace: Workspace, email: str, role: str, invited_by) -> Invitation:
    if not can_manage_invitations(workspace=workspace, user=invited_by):
        raise DomainError("Invitation creation requires admin access.")

    if role == MembershipRole.OWNER:
        raise DomainError("Invitations cannot grant the owner role.")

    normalized_email = email.strip().lower()

    if Membership.objects.filter(
        workspace=workspace,
        user__email__iexact=normalized_email,
    ).exists():
        raise DomainError("User is already a member of this workspace.")

    if Invitation.objects.filter(
        workspace=workspace,
        email__iexact=normalized_email,
        accepted_at__isnull=True,
    ).exists():
        raise DomainError("An active invitation already exists for this email.")

    return Invitation.objects.create(
        workspace=workspace,
        email=normalized_email,
        role=role,
        invited_by=invited_by,
    )


@transaction.atomic
def accept_invitation(*, invitation: Invitation, user) -> Membership:
    if invitation.accepted_at is not None:
        raise DomainError("Invitation has already been accepted.")

    if invitation.expires_at <= timezone.now():
        raise DomainError("Invitation has expired.")

    if Membership.objects.filter(workspace=invitation.workspace, user=user).exists():
        raise DomainError("User is already a member of this workspace.")

    user_email = getattr(user, "email", "").strip().lower()
    if not user_email:
        raise DomainError("A verified email is required to accept this invitation.")

    if invitation.email.strip().lower() != user_email:
        raise DomainError("This invitation is intended for a different email address.")

    membership = Membership.objects.create(
        workspace=invitation.workspace,
        user=user,
        role=invitation.role,
    )
    invitation.accepted_at = timezone.now()
    invitation.save(update_fields=["accepted_at"])
    return membership


@transaction.atomic
def revoke_invitation(*, invitation: Invitation, actor) -> None:
    if not can_manage_invitations(workspace=invitation.workspace, user=actor):
        raise DomainError("Invitation revocation requires admin access.")

    if invitation.accepted_at is not None:
        raise DomainError("Accepted invitations cannot be revoked.")

    invitation.delete()


@transaction.atomic
def change_membership_role(*, membership: Membership, role: str, actor) -> Membership:
    if not can_manage_membership(membership=membership, user=actor):
        raise DomainError("Membership role changes require elevated access.")

    if membership.role == MembershipRole.OWNER:
        raise DomainError("Owner membership cannot be changed.")

    if role == MembershipRole.OWNER:
        raise DomainError("Owner role can only be assigned during workspace creation.")

    membership.role = role
    membership.save(update_fields=["role"])
    return membership


@transaction.atomic
def transfer_workspace_ownership(
    *,
    workspace: Workspace,
    new_owner_membership: Membership,
    actor,
) -> Workspace:
    if not can_transfer_workspace_ownership(workspace=workspace, user=actor):
        raise DomainError("Ownership transfer requires the current workspace owner.")

    if new_owner_membership.workspace_id != workspace.id:
        raise DomainError("New owner must already be a member of this workspace.")

    current_owner_membership = Membership.objects.get(
        workspace=workspace,
        user=workspace.owner,
        role=MembershipRole.OWNER,
    )
    if new_owner_membership.id == current_owner_membership.id:
        return workspace

    current_owner_membership.role = MembershipRole.ADMIN
    current_owner_membership.save(update_fields=["role"])

    new_owner_membership.role = MembershipRole.OWNER
    new_owner_membership.save(update_fields=["role"])

    workspace.owner = new_owner_membership.user
    workspace.save(update_fields=["owner", "updated_at"])
    return workspace


@transaction.atomic
def remove_membership(*, membership: Membership, actor) -> None:
    if not can_manage_membership(membership=membership, user=actor):
        raise DomainError("Membership removal requires elevated access.")

    if membership.role == MembershipRole.OWNER:
        raise DomainError("Owner membership cannot be removed.")

    membership.delete()


@transaction.atomic
def delete_workspace(*, workspace: Workspace, actor) -> None:
    if not can_delete_workspace(workspace=workspace, user=actor):
        raise DomainError("Workspace deletion requires the current workspace owner.")

    workspace.delete()


def ensure_workspace_access(*, membership: Membership | None) -> Membership:
    if membership is None:
        raise DomainError("Workspace access denied.")
    return membership


def ensure_workspace_admin(*, membership: Membership | None) -> Membership:
    if not has_membership_role(membership, MembershipRole.OWNER, MembershipRole.ADMIN):
        raise DomainError("Admin access required.")
    return membership
