from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from core.health import get_liveness_status, get_readiness_status
from core.selectors import get_home_dashboard
from projects.selectors import get_user_projects
from tasks.models import TaskPriority, TaskStatus
from tasks.selectors import get_user_tasks
from workspaces.models import Invitation
from workspaces.selectors import get_user_workspaces


class HomeView(TemplateView):
    template_name = "home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            context["dashboard"] = get_home_dashboard(user=self.request.user)
        return context


class HealthCheckView(View):
    def get(self, request, *args, **kwargs):
        return JsonResponse(get_liveness_status())


class ReadinessCheckView(View):
    def get(self, request, *args, **kwargs):
        payload = get_readiness_status()
        status_code = 200 if payload["status"] == "ok" else 503
        return JsonResponse(payload, status=status_code)


class EcosystemSummaryView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        today = timezone.localdate()
        user_workspaces = get_user_workspaces(request.user)
        active_projects = get_user_projects(request.user).filter(is_archived=False)
        open_tasks = get_user_tasks(request.user).exclude(status=TaskStatus.DONE)
        overdue_tasks = open_tasks.filter(due_date__lt=today)
        user_invites = Invitation.objects.filter(
            workspace__in=user_workspaces, accepted_at__isnull=True
        )
        latest_tasks = open_tasks.order_by("-updated_at", "-created_at")[:3]

        return JsonResponse(
            {
                "service": "team_task_manager",
                "status": "ok",
                "generated_at": timezone.now().isoformat(),
                "metrics": [
                    {"label": "Workspaces", "value": user_workspaces.count()},
                    {"label": "Active projects", "value": active_projects.count()},
                    {"label": "Open tasks", "value": open_tasks.count()},
                    {"label": "Overdue tasks", "value": overdue_tasks.count()},
                    {
                        "label": "High priority",
                        "value": open_tasks.filter(priority=TaskPriority.HIGH).count(),
                    },
                    {
                        "label": "Open invites",
                        "value": user_invites.count(),
                    },
                ],
                "recent_items": [
                    {
                        "label": task.title,
                        "detail": f"{task.get_status_display()} in {task.project.name}",
                        "url": reverse(
                            "task-detail",
                            kwargs={
                                "workspace_slug": task.project.workspace.slug,
                                "project_slug": task.project.slug,
                                "task_slug": task.slug,
                            },
                        ),
                    }
                    for task in latest_tasks
                ],
                "links": [
                    {"label": "Workspaces", "url": reverse("workspace-list")},
                    {"label": "API docs", "url": reverse("api-docs")},
                ],
            }
        )
