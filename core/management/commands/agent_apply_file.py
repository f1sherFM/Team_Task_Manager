import json

from django.core.management.base import BaseCommand, CommandError

from core.agent import execute_agent_file_request
from core.exceptions import DomainError


class Command(BaseCommand):
    help = "Apply a structured local request file through Django domain services."

    def add_arguments(self, parser):
        parser.add_argument("--actor", required=True, help="Username or email for the acting user.")
        parser.add_argument("--file", required=True, help="Path to a UTF-8 text or markdown brief.")
        parser.add_argument(
            "--preview",
            action="store_true",
            help="Resolve and validate the file without creating any records.",
        )

    def handle(self, *args, **options):
        try:
            payload = execute_agent_file_request(
                actor_ref=options["actor"],
                file_path=options["file"],
                preview=options["preview"],
            )
        except DomainError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(payload, indent=2))
