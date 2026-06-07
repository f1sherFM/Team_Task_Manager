from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import redirect
from django.views import View
from django.views.generic import FormView, TemplateView

from core.exceptions import DomainError
from core.permissions import (
    can_manage_invitations,
    can_manage_membership,
    can_transfer_workspace_ownership,
)
from workspaces.forms import (
    InvitationCreateForm,
    MembershipRoleUpdateForm,
    OwnershipTransferForm,
    WorkspaceCreateForm,
)
from workspaces.models import Invitation, Membership, Workspace
from workspaces.selectors import (
    get_invitation_by_token,
    get_user_workspace_by_slug,
    get_user_workspaces,
    get_workspace_invitation_by_id,
    get_workspace_invitations,
    get_workspace_members,
    get_workspace_membership_by_id,
)
from workspaces.services import (
    accept_invitation,
    change_membership_role,
    create_invitation,
    create_workspace,
    remove_membership,
    revoke_invitation,
    transfer_workspace_ownership,
)


class WorkspaceAccessMixin(LoginRequiredMixin):
    workspace = None

    def dispatch(self, request, *args, **kwargs):
        try:
            self.workspace = get_user_workspace_by_slug(
                slug=kwargs["slug"],
                user=request.user,
            )
        except Workspace.DoesNotExist as exc:
            raise Http404("Workspace not found.") from exc
        return super().dispatch(request, *args, **kwargs)


class WorkspaceListView(LoginRequiredMixin, TemplateView):
    template_name = "workspaces/workspace_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["workspaces"] = get_user_workspaces(self.request.user)
        return context


class WorkspaceCreateView(LoginRequiredMixin, FormView):
    form_class = WorkspaceCreateForm
    template_name = "workspaces/workspace_form.html"

    def form_valid(self, form):
        workspace = create_workspace(
            owner=self.request.user,
            name=form.cleaned_data["name"],
        )
        messages.success(self.request, "Workspace created.")
        return redirect("workspace-detail", slug=workspace.slug)


class WorkspaceDetailView(WorkspaceAccessMixin, TemplateView):
    template_name = "workspaces/workspace_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["workspace"] = self.workspace
        return context


class WorkspaceMembersView(WorkspaceAccessMixin, FormView):
    form_class = InvitationCreateForm
    template_name = "workspaces/workspace_members.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["workspace"] = self.workspace
        context["memberships"] = get_workspace_members(self.workspace)
        context["invitations"] = get_workspace_invitations(self.workspace)
        context["manageable_membership_ids"] = {
            membership.id
            for membership in context["memberships"]
            if can_manage_membership(membership=membership, user=self.request.user)
            and membership.role != "owner"
        }
        context["can_manage_invitations"] = can_manage_invitations(
            workspace=self.workspace,
            user=self.request.user,
        )
        context["can_transfer_workspace_ownership"] = can_transfer_workspace_ownership(
            workspace=self.workspace,
            user=self.request.user,
        )
        context["membership_role_form"] = MembershipRoleUpdateForm()
        context["ownership_transfer_form"] = OwnershipTransferForm()
        return context

    def form_valid(self, form):
        if not can_manage_invitations(workspace=self.workspace, user=self.request.user):
            form.add_error(None, "Invitation creation requires admin access.")
            return self.form_invalid(form)

        try:
            create_invitation(
                workspace=self.workspace,
                email=form.cleaned_data["email"],
                role=form.cleaned_data["role"],
                invited_by=self.request.user,
            )
        except DomainError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)

        messages.success(self.request, "Invitation created.")
        return redirect("workspace-members", slug=self.workspace.slug)


class WorkspaceMembershipRoleUpdateView(WorkspaceAccessMixin, FormView):
    form_class = MembershipRoleUpdateForm

    def form_valid(self, form):
        try:
            membership = get_workspace_membership_by_id(
                workspace=self.workspace,
                membership_id=self.kwargs["membership_id"],
            )
            change_membership_role(
                membership=membership,
                role=form.cleaned_data["role"],
                actor=self.request.user,
            )
        except (Membership.DoesNotExist, DomainError) as exc:
            messages.error(self.request, str(exc))
            return redirect("workspace-members", slug=self.workspace.slug)

        messages.success(self.request, "Membership role updated.")
        return redirect("workspace-members", slug=self.workspace.slug)


class WorkspaceMembershipRemoveView(WorkspaceAccessMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            membership = get_workspace_membership_by_id(
                workspace=self.workspace,
                membership_id=self.kwargs["membership_id"],
            )
            remove_membership(membership=membership, actor=request.user)
        except (Membership.DoesNotExist, DomainError) as exc:
            messages.error(request, str(exc))
            return redirect("workspace-members", slug=self.workspace.slug)

        messages.success(request, "Membership removed.")
        return redirect("workspace-members", slug=self.workspace.slug)


class WorkspaceInvitationRevokeView(WorkspaceAccessMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            invitation = get_workspace_invitation_by_id(
                workspace=self.workspace,
                invitation_id=self.kwargs["invitation_id"],
            )
            revoke_invitation(invitation=invitation, actor=request.user)
        except (Invitation.DoesNotExist, DomainError) as exc:
            messages.error(request, str(exc))
            return redirect("workspace-members", slug=self.workspace.slug)

        messages.success(request, "Invitation revoked.")
        return redirect("workspace-members", slug=self.workspace.slug)


class WorkspaceOwnershipTransferView(WorkspaceAccessMixin, FormView):
    form_class = OwnershipTransferForm

    def form_valid(self, form):
        try:
            membership = get_workspace_membership_by_id(
                workspace=self.workspace,
                membership_id=form.cleaned_data["membership_id"],
            )
            transfer_workspace_ownership(
                workspace=self.workspace,
                new_owner_membership=membership,
                actor=self.request.user,
            )
        except (Membership.DoesNotExist, DomainError) as exc:
            messages.error(self.request, str(exc))
            return redirect("workspace-members", slug=self.workspace.slug)

        messages.success(self.request, "Workspace ownership transferred.")
        return redirect("workspace-members", slug=self.workspace.slug)


class InvitationAcceptView(LoginRequiredMixin, TemplateView):
    template_name = "workspaces/invitation_accept.html"
    invitation = None

    def dispatch(self, request, *args, **kwargs):
        try:
            self.invitation = get_invitation_by_token(token=kwargs["token"])
        except Invitation.DoesNotExist as exc:
            raise Http404("Invitation not found.") from exc
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["invitation"] = self.invitation
        return context

    def post(self, request, *args, **kwargs):
        try:
            accept_invitation(invitation=self.invitation, user=request.user)
        except DomainError as exc:
            messages.error(request, str(exc))
            return redirect("invitation-accept", token=self.invitation.token)

        messages.success(
            request,
            (
                f"You joined {self.invitation.workspace.name} as "
                f"{self.invitation.get_role_display().lower()}."
            ),
        )
        return redirect("workspace-detail", slug=self.invitation.workspace.slug)
