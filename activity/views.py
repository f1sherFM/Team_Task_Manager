from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.views.generic import TemplateView

from activity.selectors import get_workspace_activity
from workspaces.models import Workspace
from workspaces.selectors import get_user_workspace_by_slug


class WorkspaceActivityView(LoginRequiredMixin, TemplateView):
    template_name = "activity/workspace_activity.html"
    workspace = None

    def dispatch(self, request, *args, **kwargs):
        try:
            self.workspace = get_user_workspace_by_slug(slug=kwargs["slug"], user=request.user)
        except Workspace.DoesNotExist as exc:
            raise Http404("Workspace not found.") from exc
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["workspace"] = self.workspace
        context["activity_logs"] = get_workspace_activity(self.workspace)
        return context
