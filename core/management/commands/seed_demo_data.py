import json

from django.core.management.base import BaseCommand, CommandError

from core.logging_utils import context_extra, get_ttm_logger
from core.seed import DEFAULT_DEMO_PASSWORD, seed_demo_data

logger = get_ttm_logger("seed_command")


class Command(BaseCommand):
    help = "Create or refresh deterministic demo data for local development and demos."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default=DEFAULT_DEMO_PASSWORD,
            help="Password to assign to the seeded demo users.",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing demo workspace/users before reseeding.",
        )

    def handle(self, *args, **options):
        try:
            payload = seed_demo_data(
                password=options["password"],
                reset=options["reset"],
            )
        except Exception as exc:  # pragma: no cover - defensive command boundary
            logger.exception("seed_demo_data_failed", extra=context_extra(action="seed_demo_data"))
            raise CommandError(str(exc)) from exc

        logger.info(
            "seed_demo_data_succeeded",
            extra=context_extra(
                workspace=payload["workspace_slug"],
                user="demo_ui",
                action="seed_demo_data",
            ),
        )
        self.stdout.write(json.dumps(payload, indent=2))
