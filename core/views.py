from django.http import JsonResponse
from django.views import View
from django.views.generic import TemplateView

from core.health import get_liveness_status, get_readiness_status
from core.selectors import get_home_dashboard


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
