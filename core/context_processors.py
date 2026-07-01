from django.conf import settings


def ecosystem(_request):
    return {
        "ecosystem_apps": settings.ECOSYSTEM_APPS,
        "ecosystem_current_service": settings.ECOSYSTEM_CURRENT_SERVICE,
        "ecosystem_urls": settings.ECOSYSTEM_URLS,
    }
