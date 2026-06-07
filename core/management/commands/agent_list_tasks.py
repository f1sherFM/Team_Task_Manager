import json

from django.core.management.base import BaseCommand, CommandError

from core.agent import list_tasks_for_agent
from core.exceptions import DomainError


class Command(BaseCommand):
    help = "List tasks in a workspace project for agent automation."

    def add_arguments(self, parser):
        parser.add_argument("--actor", required=True, help="Username or email for the acting user.")
        parser.add_argument("--workspace", required=True, help="Workspace slug or visible name.")
        parser.add_argument("--project", required=True, help="Project slug or visible name.")

    def handle(self, *args, **options):
        try:
            payload = list_tasks_for_agent(
                actor_ref=options["actor"],
                workspace_ref=options["workspace"],
                project_ref=options["project"],
            )
        except DomainError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(payload, indent=2))
