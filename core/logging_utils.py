import logging


class ContextFormatter(logging.Formatter):
    context_keys = ("workspace", "project", "task", "user", "action")

    def format(self, record):
        for key in self.context_keys:
            if not hasattr(record, key):
                setattr(record, key, "-")
        return super().format(record)


def normalize_log_value(value) -> str:
    if value is None or value == "":
        return "-"
    return str(value)


def context_extra(**context) -> dict:
    return {key: normalize_log_value(value) for key, value in context.items()}


def get_ttm_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"ttm.{name}")
