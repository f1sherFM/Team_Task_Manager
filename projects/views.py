from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import redirect
from django.views.generic import FormView, TemplateView, View

from core.exceptions import DomainError
from core.permissions import can_archive_project, can_create_project
from projects.forms import ProjectCreateForm
from projects.models import Project
from projects.selectors import (
    get_workspace_project_by_slug,
    get_workspace_projects,
)
from projects.services import archive_project, create_project, unarchive_project
from workspaces.models import Workspace
from workspaces.selectors import get_user_workspace_by_slug


class WorkspaceProjectAccessMixin(LoginRequiredMixin):
    workspace = None

    def dispatch(self, request, *args, **kwargs):
        try:
            self.workspace = get_user_workspace_by_slug(
                slug=kwargs["workspace_slug"],
                user=request.user,
            )
        except Workspace.DoesNotExist as exc:
            raise Http404("Workspace not found.") from exc
        return super().dispatch(request, *args, **kwargs)


class ProjectAccessMixin(LoginRequiredMixin):
    project = None

    def dispatch(self, request, *args, **kwargs):
        try:
            self.project = get_workspace_project_by_slug(
                workspace_slug=kwargs["workspace_slug"],
                project_slug=kwargs["project_slug"],
                user=request.user,
            )
        except Project.DoesNotExist as exc:
            raise Http404("Project not found.") from exc
        return super().dispatch(request, *args, **kwargs)


class WorkspaceProjectListView(WorkspaceProjectAccessMixin, FormView):
    form_class = ProjectCreateForm
    template_name = "projects/project_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["workspace"] = self.workspace
        context["projects"] = get_workspace_projects(workspace=self.workspace)
        context["can_create_project"] = can_create_project(
            workspace=self.workspace,
            user=self.request.user,
        )
        return context

    def form_valid(self, form):
        if not can_create_project(workspace=self.workspace, user=self.request.user):
            raise PermissionDenied("Project creation requires admin access.")

        project = create_project(
            workspace=self.workspace,
            name=form.cleaned_data["name"],
            description=form.cleaned_data["description"],
            created_by=self.request.user,
        )
        messages.success(self.request, "Project created.")
        return redirect(
            "project-detail",
            workspace_slug=project.workspace.slug,
            project_slug=project.slug,
        )


class ProjectDetailView(ProjectAccessMixin, TemplateView):
    template_name = "projects/project_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["project"] = self.project
        context["can_archive_project"] = can_archive_project(
            project=self.project,
            user=self.request.user,
        )
        return context


class ProjectArchiveView(ProjectAccessMixin, View):
    target_state = True
    success_message = "Project archived."

    def post(self, request, *args, **kwargs):
        try:
            if self.target_state:
                archive_project(project=self.project, actor=request.user)
            else:
                unarchive_project(project=self.project, actor=request.user)
        except DomainError as exc:
            raise PermissionDenied(str(exc)) from exc

        messages.success(request, self.success_message)
        return redirect(
            "project-detail",
            workspace_slug=self.project.workspace.slug,
            project_slug=self.project.slug,
        )


class ProjectUnarchiveView(ProjectArchiveView):
    target_state = False
    success_message = "Project restored."
