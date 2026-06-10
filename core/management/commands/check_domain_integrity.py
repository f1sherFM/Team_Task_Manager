from django.core.management.base import BaseCommand, CommandError

from core.integrity import run_integrity_checks
from core.logging_utils import context_extra, get_ttm_logger

logger = get_ttm_logger("integrity")


class Command(BaseCommand):
    help = "Validate core domain invariants and exit non-zero when issues are found."

    def handle(self, *args, **options):
        issues = run_integrity_checks()
        if issues:
            logger.error(
                "domain_integrity_failed",
                extra=context_extra(action="check_domain_integrity"),
            )
            for issue in issues:
                self.stderr.write(f"ERROR: {issue}")
            raise CommandError(f"Found {len(issues)} integrity issue(s).")

        logger.info(
            "domain_integrity_passed",
            extra=context_extra(action="check_domain_integrity"),
        )
        self.stdout.write("Integrity check passed.")
