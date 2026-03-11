from django.utils.text import slugify


def generate_slug(value: str) -> str:
    return slugify(value).strip("-")
