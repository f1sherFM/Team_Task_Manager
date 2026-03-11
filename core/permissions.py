from django.contrib.auth.models import AnonymousUser


def is_authenticated(user) -> bool:
    return bool(user and not isinstance(user, AnonymousUser) and user.is_authenticated)
