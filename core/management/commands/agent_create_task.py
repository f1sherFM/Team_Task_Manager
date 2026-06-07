import json

from django.core.management.base import BaseCommand, CommandError

from core.agent import create_task_for_agent
from core.exceptions import DomainError


class Command(BaseCommand):
    help = "Create a task through Django domain services without using the API."

    def add_arguments(self, parser):
        parser.add_argument("--actor", required=True, help="Username or email for the acting user.")
        parser.add_argument("--workspace", required=True, help="Workspace slug or visible name.")
        parser.add_argument("--project", required=True, help="Project slug or visible name.")
        parser.add_argument("--title", required=True, help="Task title.")
        parser.add_argument("--description", default="", help="Optional task description.")
        parser.add_argument("--priority", default="medium", help="low, medium, or high.")
        parser.add_argument("--due-date", dest="due_date", help="YYYY-MM-DD due date.")
        parser.add_argument("--assignee", help="Optional assignee username or email.")
        parser.add_argument("--status", default="todo", help="todo, in_progress, or done.")

    def handle(self, *args, **options):
        try:
            task = create_task_for_agent(
                actor_ref=options["actor"],
                workspace_ref=options["workspace"],
                project_ref=options["project"],
                title=options["title"],
                description=options["description"],
                priority=options["priority"],
                due_date=options["due_date"],
                assignee_ref=options["assignee"],
                status=options["status"],
            )
        except DomainError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            json.dumps(
                {
                    "workspace": task.project.workspace.slug,
                    "project": task.project.slug,
                    "task": task.slug,
                    "title": task.title,
                    "status": task.status,
                },
                indent=2,
            )
        )
