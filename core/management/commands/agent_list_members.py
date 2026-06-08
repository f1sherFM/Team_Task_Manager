import json

from django.core.management.base import BaseCommand, CommandError

from core.agent import list_members_for_agent
from core.exceptions import DomainError


class Command(BaseCommand):
    help = "List workspace members available to an actor for Codex-style automation."

    def add_arguments(self, parser):
        parser.add_argument("--actor", required=True, help="Username or email for the acting user.")
        parser.add_argument("--workspace", required=True, help="Workspace slug or name.")

    def handle(self, *args, **options):
        try:
            payload = list_members_for_agent(
                actor_ref=options["actor"],
                workspace_ref=options["workspace"],
            )
        except DomainError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(payload, indent=2))
