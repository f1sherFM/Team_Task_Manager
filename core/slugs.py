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
