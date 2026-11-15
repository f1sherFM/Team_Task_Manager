import re

from django.core.exceptions import ValidationError

HEX_COLOR_REGEX = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def validate_hex_color(value: str) -> None:
    if not isinstance(value, str) or not HEX_COLOR_REGEX.match(value.strip()):
        raise ValidationError(
            f"'{value}' is not a valid HEX color code. Expected format: #RGB or #RRGGBB."
        )
