import json

from django.core.management.base import BaseCommand, CommandError

from core.agent import create_project_for_agent
from core.exceptions import DomainError


class Command(BaseCommand):
    help = "Create a project through Django domain services without using the API."

    def add_arguments(self, parser):
        parser.add_argument("--actor", required=True, help="Username or email for the acting user.")
        parser.add_argument("--workspace", required=True, help="Workspace slug or visible name.")
        parser.add_argument("--name", required=True, help="Project name.")
        parser.add_argument(
            "--description",
            default="",
            help="Optional project description.",
        )

    def handle(self, *args, **options):
        try:
            project = create_project_for_agent(
                actor_ref=options["actor"],
                workspace_ref=options["workspace"],
                name=options["name"],
                description=options["description"],
            )
        except DomainError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            json.dumps(
                {
                    "workspace": project.workspace.slug,
                    "project": project.slug,
                    "name": project.name,
                },
                indent=2,
            )
        )
