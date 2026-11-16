from django import template
from django.utils import timezone

register = template.Library()


@register.simple_tag(takes_context=True)
def url_replace(context, **kwargs):
    request = context.get("request")
    if not request:
        return ""
    query = request.GET.copy()
    for key, value in kwargs.items():
        if value is None or value == "":
            query.pop(key, None)
        else:
            query[key] = str(value)
    return query.urlencode()


@register.filter
def checklist_progress(task):
    if not hasattr(task, "checklist_items"):
        return ""
    items = task.checklist_items.all()
    total = len(items)
    if not total:
        return ""
    completed = sum(1 for item in items if item.is_completed)
    return f"{completed}/{total}"


@register.filter
def is_task_overdue(task):
    if not getattr(task, "due_date", None):
        return False
    return task.due_date < timezone.localdate() and task.status != "done"

