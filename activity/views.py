from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.http import Http404
from django.views.generic import TemplateView

from activity.selectors import get_workspace_activity
from workspaces.models import Workspace
from workspaces.selectors import get_user_workspace_by_slug


class WorkspaceActivityView(LoginRequiredMixin, TemplateView):
    template_name = "activity/workspace_activity.html"
    workspace = None

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        try:
            self.workspace = get_user_workspace_by_slug(slug=kwargs["slug"], user=request.user)
        except Workspace.DoesNotExist as exc:
            raise Http404("Workspace not found.") from exc
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        activity_qs = get_workspace_activity(self.workspace)
        paginator = Paginator(activity_qs, 25)
        page_obj = paginator.get_page(self.request.GET.get("page"))
        context["workspace"] = self.workspace
        context["activity_logs"] = page_obj
        context["page_obj"] = page_obj
        context["is_paginated"] = page_obj.has_other_pages()
        return context
