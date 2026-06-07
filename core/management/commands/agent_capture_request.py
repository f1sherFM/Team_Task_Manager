import json

from django.core.management.base import BaseCommand, CommandError

from core.agent import execute_agent_batch_request
from core.exceptions import DomainError


class Command(BaseCommand):
    help = "Capture a high-level Codex request and execute it through Django services."

    def add_arguments(self, parser):
        parser.add_argument("--actor", required=True, help="Username or email for the acting user.")
        parser.add_argument(
            "--request",
            required=True,
            help="Structured or natural-language request describing the project or task to create.",
        )
        parser.add_argument(
            "--preview",
            action="store_true",
            help="Resolve and validate the request without creating any records.",
        )

    def handle(self, *args, **options):
        try:
            payload = execute_agent_batch_request(
                actor_ref=options["actor"],
                request_text=options["request"],
                preview=options["preview"],
            )
        except DomainError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(payload, indent=2))
