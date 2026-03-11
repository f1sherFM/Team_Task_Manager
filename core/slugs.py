from django.db import IntegrityError
from django.utils.text import slugify


def generate_slug(value: str) -> str:
    return slugify(value).strip("-")


def generate_unique_slug(*, model, value: str, slug_field: str = "slug", scope: dict | None = None) -> str:
    base_slug = generate_slug(value) or "item"
    slug = base_slug
    counter = 2
    filters = scope or {}

    while model.objects.filter(**filters, **{slug_field: slug}).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1

    return slug


def create_with_unique_slug(
    *,
    model,
    value: str,
    create_kwargs: dict,
    slug_field: str = "slug",
    scope: dict | None = None,
    max_attempts: int = 8,
):
    last_error = None

    for _ in range(max_attempts):
        slug = generate_unique_slug(
            model=model,
            value=value,
            slug_field=slug_field,
            scope=scope,
        )
        try:
            return model.objects.create(**create_kwargs, **{slug_field: slug})
        except IntegrityError as exc:
            last_error = exc

    if last_error is not None:
        raise last_error
