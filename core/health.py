from django.db import connections
from django.db.migrations.executor import MigrationExecutor


def check_database() -> dict:
    connection = connections["default"]
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()
    return {"status": "ok"}


def check_migrations() -> dict:
    connection = connections["default"]
    executor = MigrationExecutor(connection)
    targets = executor.loader.graph.leaf_nodes()
    plan = executor.migration_plan(targets)
    if plan:
        pending_migrations = [
            f"{migration.app_label}.{migration.name}" for migration, _ in plan
        ]
        return {
            "status": "out_of_date",
            "pending_migrations": pending_migrations,
        }
    return {"status": "ok"}


def get_liveness_status() -> dict:
    return {"status": "ok"}


def get_readiness_status() -> dict:
    database = check_database()
    migrations = check_migrations()
    checks = {
        "database": database,
        "migrations": migrations,
    }
    overall_status = "ok" if all(check["status"] == "ok" for check in checks.values()) else "error"
    return {"status": overall_status, "checks": checks}
