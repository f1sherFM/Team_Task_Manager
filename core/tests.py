import json
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase

from core.agent import (
    close_task_for_agent,
    create_project_for_agent,
    create_task_for_agent,
    execute_agent_batch_request,
    execute_agent_file_request,
    execute_agent_request,
    expand_agent_request_text,
    parse_markdown_brief,
    preview_agent_request,
    update_task_for_agent,
)
from core.health import get_readiness_status
from projects.services import create_project
from tasks.models import TaskPriority, TaskStatus
from workspaces.models import Membership, MembershipRole
from workspaces.services import create_workspace


class HealthEndpointTests(TestCase):
    def test_healthz_returns_ok(self):
        response = self.client.get("/healthz/")

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"status": "ok"})

    def test_readyz_returns_ok_when_dependencies_are_healthy(self):
        response = self.client.get("/readyz/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(response.json()["checks"]["database"]["status"], "ok")
        self.assertEqual(response.json()["checks"]["migrations"]["status"], "ok")


class ReadinessStatusTests(SimpleTestCase):
    @patch("core.health.check_migrations")
    @patch("core.health.check_database")
    def test_readiness_status_reports_error_when_dependency_fails(
        self,
        mock_check_database,
        mock_check_migrations,
    ):
        mock_check_database.return_value = {"status": "ok"}
        mock_check_migrations.return_value = {
            "status": "out_of_date",
            "pending_migrations": ["tasks.0003_example"],
        }

        payload = get_readiness_status()

        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["checks"]["database"]["status"], "ok")
        self.assertEqual(payload["checks"]["migrations"]["status"], "out_of_date")
        self.assertEqual(
            payload["checks"]["migrations"]["pending_migrations"],
            ["tasks.0003_example"],
        )


class AgentAutomationTests(TestCase):
    def setUp(self):
        self.stdout = StringIO()
        self.test_request_file = Path("C:/Team_Task_Manager/tmp_agent_request.txt")
        self.User = get_user_model()
        self.owner = self.User.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="secret123",
        )
        self.member = self.User.objects.create_user(
            username="member",
            email="member@example.com",
            password="secret123",
        )
        self.workspace = create_workspace(owner=self.owner, name="Engineering")
        Membership.objects.create(
            workspace=self.workspace,
            user=self.member,
            role=MembershipRole.MEMBER,
        )
        self.project = create_project(
            workspace=self.workspace,
            name="Backend Platform",
            description="Primary backend project",
            created_by=self.owner,
        )

    def tearDown(self):
        if self.test_request_file.exists():
            self.test_request_file.unlink()

    def test_create_project_for_agent_uses_domain_services(self):
        project = create_project_for_agent(
            actor_ref="owner",
            workspace_ref=self.workspace.slug,
            name="API Expansion",
            description="Add new internal tooling",
        )

        self.assertEqual(project.workspace, self.workspace)
        self.assertEqual(project.created_by, self.owner)

    def test_create_task_for_agent_supports_name_resolution(self):
        task = create_task_for_agent(
            actor_ref="owner@example.com",
            workspace_ref="Engineering",
            project_ref="Backend Platform",
            title="Ship agent CLI",
            description="Create commands for Codex",
            priority=TaskPriority.HIGH,
            assignee_ref="member",
            due_date="2026-06-08",
        )

        self.assertEqual(task.project, self.project)
        self.assertEqual(task.assignee, self.member)
        self.assertEqual(task.priority, TaskPriority.HIGH)
        self.assertEqual(task.due_date.isoformat(), "2026-06-08")

    def test_execute_agent_request_supports_structured_task_request(self):
        payload = execute_agent_request(
            actor_ref="owner",
            request_text=(
                "action: create_task\n"
                "workspace: Engineering\n"
                "project: Backend Platform\n"
                "title: Add audit export\n"
                "description: Build an export command for activity logs\n"
                "priority: medium\n"
                "assignee: member\n"
            ),
        )

        self.assertEqual(payload["action"], "create_task")
        self.assertEqual(payload["workspace"], self.workspace.slug)
        self.assertEqual(payload["project"], self.project.slug)

    def test_execute_agent_request_supports_russian_structured_task_request(self):
        payload = execute_agent_request(
            actor_ref="owner",
            request_text=(
                "действие: создать задачу\n"
                "воркспейс: Engineering\n"
                "проект: Backend Platform\n"
                "название: Добавить русскоязычный парсер\n"
                "описание: Проверить русские алиасы\n"
                "приоритет: высокий\n"
                "исполнитель: member\n"
                "статус: в работе\n"
            ),
        )

        self.assertEqual(payload["action"], "create_task")
        self.assertEqual(payload["workspace"], self.workspace.slug)
        self.assertEqual(payload["project"], self.project.slug)
        self.assertEqual(payload["status"], TaskStatus.IN_PROGRESS)

    def test_agent_list_workspaces_command_outputs_json(self):
        call_command(
            "agent_list_workspaces",
            actor="owner",
            stdout=self.stdout,
        )

        payload = json.loads(self.stdout.getvalue())
        self.assertEqual(payload[0]["slug"], self.workspace.slug)

    def test_agent_create_task_command_creates_task(self):
        call_command(
            "agent_create_task",
            actor="owner",
            workspace=self.workspace.slug,
            project=self.project.slug,
            title="Document CLI flow",
            description="Write down the agent workflow",
            priority="medium",
            stdout=self.stdout,
        )

        payload = json.loads(self.stdout.getvalue())
        self.assertEqual(payload["project"], self.project.slug)
        self.assertEqual(payload["title"], "Document CLI flow")

    def test_update_task_for_agent_updates_existing_task(self):
        task = create_task_for_agent(
            actor_ref="owner",
            workspace_ref=self.workspace.slug,
            project_ref=self.project.slug,
            title="Refine import flow",
        )

        updated_task = update_task_for_agent(
            actor_ref="owner",
            workspace_ref=self.workspace.slug,
            project_ref=self.project.slug,
            task_ref=task.slug,
            description="Updated by agent",
            status=TaskStatus.IN_PROGRESS,
        )

        self.assertEqual(updated_task.description, "Updated by agent")
        self.assertEqual(updated_task.status, TaskStatus.IN_PROGRESS)

    def test_close_task_for_agent_marks_task_done(self):
        task = create_task_for_agent(
            actor_ref="owner",
            workspace_ref=self.workspace.slug,
            project_ref=self.project.slug,
            title="Close me",
        )

        closed_task = close_task_for_agent(
            actor_ref="owner",
            workspace_ref=self.workspace.slug,
            project_ref=self.project.slug,
            task_ref=task.title,
        )

        self.assertEqual(closed_task.status, TaskStatus.DONE)

    def test_agent_capture_request_command_rejects_unsupported_request(self):
        with self.assertRaises(CommandError):
            call_command(
                "agent_capture_request",
                actor="owner",
                request="please do something vague",
                stdout=self.stdout,
            )

    def test_preview_agent_request_resolves_slugs_without_writes(self):
        payload = preview_agent_request(
            actor_ref="owner",
            request_text=(
                "action: create_task\n"
                "workspace: Engineering\n"
                "project: Backend Platform\n"
                "title: Preview agent flow\n"
                "assignee: member\n"
            ),
        )

        self.assertEqual(payload["workspace_slug"], self.workspace.slug)
        self.assertEqual(payload["project_slug"], self.project.slug)
        self.assertEqual(payload["assignee_username"], self.member.username)

    def test_execute_agent_batch_request_handles_multiple_blocks(self):
        payload = execute_agent_batch_request(
            actor_ref="owner",
            request_text=(
                "action: create_project\n"
                "workspace: Engineering\n"
                "name: Agent Extensions\n"
                "---\n"
                "action: create_task\n"
                "workspace: Engineering\n"
                "project: Backend Platform\n"
                "title: Add batch automation support\n"
            ),
        )

        self.assertEqual(len(payload), 2)
        self.assertEqual(payload[0]["action"], "create_project")
        self.assertEqual(payload[1]["action"], "create_task")

    def test_execute_agent_batch_request_preview_supports_future_project(self):
        payload = execute_agent_batch_request(
            actor_ref="owner",
            request_text=(
                "action: create_project\n"
                "workspace: Engineering\n"
                "name: Preview Project\n"
                "---\n"
                "action: create_task\n"
                "workspace: Engineering\n"
                "project: Preview Project\n"
                "title: Preview task against future project\n"
            ),
            preview=True,
        )

        self.assertEqual(payload[0]["project_slug"], "preview-project")
        self.assertEqual(payload[1]["project_slug"], "preview-project")

    def test_agent_capture_request_command_supports_preview(self):
        call_command(
            "agent_capture_request",
            actor="owner",
            request=(
                "action: create_task\n"
                "workspace: Engineering\n"
                "project: Backend Platform\n"
                "title: Preview-only task\n"
            ),
            preview=True,
            stdout=self.stdout,
        )

        payload = json.loads(self.stdout.getvalue())
        self.assertEqual(payload[0]["title"], "Preview-only task")
        self.assertEqual(payload[0]["project_slug"], self.project.slug)

    def test_execute_agent_file_request_reads_and_applies_file(self):
        self.test_request_file.write_text(
            "action: create_task\n"
            "workspace: Engineering\n"
            "project: Backend Platform\n"
            "title: Import task from file\n",
            encoding="utf-8",
        )

        payload = execute_agent_file_request(
            actor_ref="owner",
            file_path=str(self.test_request_file),
        )

        self.assertEqual(payload[0]["title"], "Import task from file")

    def test_agent_apply_file_command_supports_preview(self):
        self.test_request_file.write_text(
            "action: create_task\n"
            "workspace: Engineering\n"
            "project: Backend Platform\n"
            "title: Preview file task\n",
            encoding="utf-8",
        )

        call_command(
            "agent_apply_file",
            actor="owner",
            file=str(self.test_request_file),
            preview=True,
            stdout=self.stdout,
        )

        payload = json.loads(self.stdout.getvalue())
        self.assertEqual(payload[0]["title"], "Preview file task")
        self.assertEqual(payload[0]["project_slug"], self.project.slug)

    def test_parse_markdown_brief_supports_project_and_task_blocks(self):
        chunks = parse_markdown_brief(
            request_text=(
                "# Workspace: Engineering\n"
                "# Project: Agent Extensions\n"
                "Action: create_project\n"
                "Description: Tasks imported from markdown\n"
                "\n"
                "- [ ] Add parser support\n"
                "  priority: high\n"
                "  assignee: member\n"
                "- [ ] Add docs updates\n"
            )
        )

        self.assertEqual(len(chunks), 3)
        self.assertIn("action: create_project", chunks[0])
        self.assertIn("title: Add parser support", chunks[1])
        self.assertIn("title: Add docs updates", chunks[2])

    def test_parse_markdown_brief_supports_russian_metadata(self):
        chunks = parse_markdown_brief(
            request_text=(
                "Воркспейс: Engineering\n"
                "Проект: Backend Platform\n"
                "Действие для задач: update_task\n"
                "- [x] Ship markdown parser\n"
                "  задача: Ship markdown parser\n"
                "  приоритет: высокий\n"
            )
        )

        self.assertEqual(len(chunks), 1)
        self.assertIn("action: update_task", chunks[0])
        self.assertIn("status: done", chunks[0])
        self.assertIn("priority: высокий", chunks[0])

    def test_expand_agent_request_text_prefers_markdown_brief_when_no_separator(self):
        chunks = expand_agent_request_text(
            request_text=(
                "Workspace: Engineering\n"
                "Project: Backend Platform\n"
                "- Add markdown import\n"
            )
        )

        self.assertEqual(len(chunks), 1)
        self.assertIn("action: create_task", chunks[0])
        self.assertIn("title: Add markdown import", chunks[0])

    def test_execute_agent_batch_request_supports_markdown_brief(self):
        payload = execute_agent_batch_request(
            actor_ref="owner",
            request_text=(
                "Workspace: Engineering\n"
                "Project: Backend Platform\n"
                "- [ ] Ship markdown parser\n"
                "  priority: high\n"
                "  assignee: member\n"
            ),
        )

        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["action"], "create_task")
        self.assertEqual(payload[0]["project"], self.project.slug)

    def test_parse_markdown_brief_supports_task_action_metadata(self):
        chunks = parse_markdown_brief(
            request_text=(
                "Workspace: Engineering\n"
                "Project: Backend Platform\n"
                "Task Action: update_task\n"
                "- [x] Ship markdown parser\n"
                "  task: Ship markdown parser\n"
                "- [ ] Refresh docs title\n"
                "  task: Existing docs task\n"
                "  title: Refresh docs title\n"
            )
        )

        self.assertEqual(len(chunks), 2)
        self.assertIn("action: update_task", chunks[0])
        self.assertIn("status: done", chunks[0])
        self.assertIn("task: Existing docs task", chunks[1])
        self.assertIn("title: Refresh docs title", chunks[1])

    def test_execute_agent_request_supports_update_task(self):
        task = create_task_for_agent(
            actor_ref="owner",
            workspace_ref=self.workspace.slug,
            project_ref=self.project.slug,
            title="Agent update target",
        )

        payload = execute_agent_request(
            actor_ref="owner",
            request_text=(
                "action: update_task\n"
                f"workspace: {self.workspace.slug}\n"
                f"project: {self.project.slug}\n"
                f"task: {task.slug}\n"
                "status: done\n"
                "description: Completed through agent automation\n"
            ),
        )

        self.assertEqual(payload["action"], "update_task")
        self.assertEqual(payload["status"], TaskStatus.DONE)

    def test_execute_agent_batch_request_supports_markdown_update_flow(self):
        task = create_task_for_agent(
            actor_ref="owner",
            workspace_ref=self.workspace.slug,
            project_ref=self.project.slug,
            title="Ship markdown parser",
        )

        payload = execute_agent_batch_request(
            actor_ref="owner",
            request_text=(
                "Workspace: Engineering\n"
                "Project: Backend Platform\n"
                "Task Action: update_task\n"
                "- [x] Ship markdown parser\n"
                "  task: Ship markdown parser\n"
            ),
        )

        task.refresh_from_db()
        self.assertEqual(payload[0]["action"], "update_task")
        self.assertEqual(task.status, TaskStatus.DONE)

    def test_agent_update_task_command_updates_task(self):
        task = create_task_for_agent(
            actor_ref="owner",
            workspace_ref=self.workspace.slug,
            project_ref=self.project.slug,
            title="CLI update target",
        )

        call_command(
            "agent_update_task",
            actor="owner",
            workspace=self.workspace.slug,
            project=self.project.slug,
            task=task.slug,
            status="done",
            stdout=self.stdout,
        )

        payload = json.loads(self.stdout.getvalue())
        self.assertEqual(payload["task"], task.slug)
        self.assertEqual(payload["status"], TaskStatus.DONE)
