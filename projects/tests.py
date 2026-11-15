from django.contrib.auth import get_user_model
from django.test import TestCase

from core.exceptions import DomainError
from projects.services import archive_project, create_project, unarchive_project
from workspaces.models import Membership, MembershipRole
from workspaces.services import create_workspace

User = get_user_model()


class ProjectServiceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="secret123")
        self.admin = User.objects.create_user(username="admin", password="secret123")
        self.member = User.objects.create_user(username="member", password="secret123")
        self.workspace = create_workspace(owner=self.owner, name="Engineering")
        Membership.objects.create(
            workspace=self.workspace,
            user=self.admin,
            role=MembershipRole.ADMIN,
        )
        Membership.objects.create(
            workspace=self.workspace,
            user=self.member,
            role=MembershipRole.MEMBER,
        )
        self.project = create_project(
            workspace=self.workspace,
            name="Platform",
            description="Core platform",
            created_by=self.owner,
        )

    def test_workspace_member_without_admin_role_cannot_create_project(self):
        with self.assertRaises(DomainError):
            create_project(
                workspace=self.workspace,
                name="Forbidden project",
                description="No access",
                created_by=self.member,
            )

    def test_member_cannot_archive_project(self):
        with self.assertRaises(DomainError):
            archive_project(project=self.project, actor=self.member)

    def test_admin_can_archive_and_restore_project(self):
        archived_project = archive_project(project=self.project, actor=self.admin)
        self.assertTrue(archived_project.is_archived)

        restored_project = unarchive_project(project=archived_project, actor=self.admin)
        self.assertFalse(restored_project.is_archived)

    def test_project_archive_view_archives_project(self):
        self.client.login(username="owner", password="secret123")

        response = self.client.post(
            f"/workspaces/{self.workspace.slug}/projects/{self.project.slug}/archive/"
        )

        self.assertEqual(response.status_code, 302)
        self.project.refresh_from_db()
        self.assertTrue(self.project.is_archived)


class WorkspaceProjectListViewPaginationTests(TestCase):
    def setUp(self):
        from workspaces.services import create_workspace

        self.user = User.objects.create_user(username="proj_page_user", password="secret123")
        self.workspace = create_workspace(owner=self.user, name="Project Page WS")
        for i in range(15):
            create_project(
                workspace=self.workspace,
                name=f"Project {i + 1}",
                description="",
                created_by=self.user,
            )

    def test_project_list_pagination(self):
        from django.urls import reverse

        self.client.force_login(self.user)
        url = reverse(
            "workspace-project-list",
            kwargs={"workspace_slug": self.workspace.slug},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["is_paginated"])
        self.assertEqual(len(response.context["projects"]), 12)

        response_p2 = self.client.get(url + "?page=2")
        self.assertEqual(response_p2.status_code, 200)
        self.assertEqual(len(response_p2.context["projects"]), 3)

