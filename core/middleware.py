from django.http import HttpResponse
from django.urls import reverse


class HtmxSessionExpiryMiddleware:
    """
    Ensures that when an HTMX request encounters a login redirect (302) or 401/403,
    it returns an HX-Redirect header instead of sending full HTML to be swapped inside
    a partial fragment.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if request.headers.get("HX-Request") == "true":
            if response.status_code in (301, 302, 303, 307, 308):
                location = response.get("Location", "")
                if "/login" in location or "accounts/login" in location:
                    htmx_response = HttpResponse(status=200)
                    htmx_response["HX-Redirect"] = location
                    return htmx_response
            elif response.status_code == 401 or (
                response.status_code == 403
                and (not hasattr(request, "user") or not request.user.is_authenticated)
            ):
                login_url = f"{reverse('login')}?next={request.path}"
                htmx_response = HttpResponse(status=200)
                htmx_response["HX-Redirect"] = login_url
                return htmx_response

        return response
