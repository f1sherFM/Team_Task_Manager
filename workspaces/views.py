from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import redirect
from django.views.generic import FormView, TemplateView

from core.exceptions import DomainError
from core.permissions import can_manage_invitations
from workspaces.forms import InvitationCreateForm, WorkspaceCreateForm
from workspaces.models import Invitation, Workspace
from workspaces.selectors import (
    get_invitation_by_token,
    get_user_workspace_by_slug,
    get_user_workspaces,
    get_workspace_invitations,
    get_workspace_members,
)
from workspaces.services import accept_invitation, create_invitation, create_workspace


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
        context["can_manage_invitations"] = can_manage_invitations(
            workspace=self.workspace,
            user=self.request.user,
        )
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
