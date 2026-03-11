from django.db import transaction
from django.utils import timezone

from core.exceptions import DomainError
from core.permissions import has_membership_role
from core.slugs import generate_unique_slug
from workspaces.models import Invitation, Membership, MembershipRole, Workspace


@transaction.atomic
def create_workspace(*, owner, name: str) -> Workspace:
    slug = generate_unique_slug(model=Workspace, value=name)
    workspace = Workspace.objects.create(name=name, slug=slug, owner=owner)
    Membership.objects.create(workspace=workspace, user=owner, role=MembershipRole.OWNER)
    return workspace


@transaction.atomic
def create_invitation(*, workspace: Workspace, email: str, role: str, invited_by) -> Invitation:
    if role == MembershipRole.OWNER:
        raise DomainError("Invitations cannot grant the owner role.")

    if Membership.objects.filter(workspace=workspace, user__email__iexact=email).exists():
        raise DomainError("User is already a member of this workspace.")

    if Invitation.objects.filter(workspace=workspace, email__iexact=email, accepted_at__isnull=True).exists():
        raise DomainError("An active invitation already exists for this email.")

    return Invitation.objects.create(
        workspace=workspace,
        email=email,
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

    membership = Membership.objects.create(
        workspace=invitation.workspace,
        user=user,
        role=invitation.role,
    )
    invitation.accepted_at = timezone.now()
    invitation.save(update_fields=["accepted_at"])
    return membership


@transaction.atomic
def change_membership_role(*, membership: Membership, role: str) -> Membership:
    if membership.role == MembershipRole.OWNER:
        raise DomainError("Owner membership cannot be changed.")

    membership.role = role
    membership.save(update_fields=["role"])
    return membership


@transaction.atomic
def remove_membership(*, membership: Membership) -> None:
    if membership.role == MembershipRole.OWNER:
        raise DomainError("Owner membership cannot be removed.")

    membership.delete()


def ensure_workspace_access(*, membership: Membership | None) -> Membership:
    if membership is None:
        raise DomainError("Workspace access denied.")
    return membership


def ensure_workspace_admin(*, membership: Membership | None) -> Membership:
    if not has_membership_role(membership, MembershipRole.OWNER, MembershipRole.ADMIN):
        raise DomainError("Admin access required.")
    return membership
