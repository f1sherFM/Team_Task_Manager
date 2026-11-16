from django.http import HttpResponse
from django.urls import reverse


class HtmxSessionExpiryMiddleware:
    """
    Ensures that when an unauthenticated HTMX request encounters a login redirect (302) or 401/403,
    it returns an HX-Redirect header instead of sending full HTML to be swapped inside
    a partial fragment.

    Authenticated users receiving 400, 403, 404, or 500 are NEVER redirected; their response
    is preserved as-is so the frontend can display the error without losing the current page.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if request.headers.get("HX-Request") == "true":
            is_authenticated = bool(hasattr(request, "user") and request.user.is_authenticated)

            if not is_authenticated:
                if response.status_code in (301, 302, 303, 307, 308):
                    location = response.get("Location", "")
                    if "/login" in location or "accounts/login" in location:
                        htmx_response = HttpResponse(status=200)
                        htmx_response["HX-Redirect"] = location
                        return htmx_response
                elif response.status_code in (401, 403):
                    login_url = f"{reverse('login')}?next={request.path}"
                    htmx_response = HttpResponse(status=200)
                    htmx_response["HX-Redirect"] = login_url
                    return htmx_response

        return response
