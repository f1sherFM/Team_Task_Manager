from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import redirect
from django.views.generic import FormView, TemplateView

from workspaces.models import Workspace
from workspaces.forms import WorkspaceCreateForm
from workspaces.selectors import (
    get_user_workspaces,
    get_workspace_members,
    get_user_workspace_by_slug,
)
from workspaces.services import create_workspace


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


class WorkspaceMembersView(WorkspaceAccessMixin, TemplateView):
    template_name = "workspaces/workspace_members.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["workspace"] = self.workspace
        context["memberships"] = get_workspace_members(self.workspace)
        return context
