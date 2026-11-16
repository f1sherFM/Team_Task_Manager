from django.contrib.auth import get_user_model
from django.test import TestCase

from activity.models import ActivityLog
from comments.models import Comment
from comments.services import add_comment
from core.exceptions import DomainError
from core.integrity import check_checklist_item_integrity, check_task_tag_workspace_integrity
from projects.services import archive_project, create_project
from tasks.models import Task, TaskChecklistItem, TaskStatus, TaskTag
from tasks.selectors import (
    get_task_checklist_items,
    get_workspace_tag_by_id,
    get_workspace_tag_by_slug,
    get_workspace_tags,
)
from tasks.services import (
    add_checklist_item,
    archive_task,
    assign_tag_to_task,
    assign_task,
    bulk_update_tasks,
    change_task_status,
    create_task,
    create_task_tag,
    delete_checklist_item,
    delete_task,
    delete_task_tag,
    remove_tag_from_task,
    reorder_checklist_items,
    restore_task,
    set_task_tags,
    toggle_checklist_item,
    update_checklist_item,
    update_task_tag,
)
from workspaces.models import Membership, MembershipRole
from workspaces.services import create_workspace

User = get_user_model()


class TaskServiceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="secret123")
        self.admin = User.objects.create_user(username="admin", password="secret123")
        self.member = User.objects.create_user(username="member", password="secret123")
        self.other = User.objects.create_user(username="other", password="secret123")

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
        Membership.objects.create(
            workspace=self.workspace,
            user=self.other,
            role=MembershipRole.MEMBER,
        )
        self.project = create_project(
            workspace=self.workspace,
            name="API",
            description="Core API",
            created_by=self.owner,
        )

    def test_workspace_member_can_create_task(self):
        task = create_task(
            project=self.project,
            title="Implement endpoint",
            description="",
            priority="medium",
            due_date=None,
            assignee=None,
            created_by=self.member,
        )

        self.assertEqual(task.created_by, self.member)

    def test_non_admin_cannot_assign_task(self):
        task = create_task(
            project=self.project,
            title="Implement endpoint",
            description="",
            priority="medium",
            due_date=None,
            assignee=None,
            created_by=self.member,
        )

        with self.assertRaises(DomainError):
            assign_task(task=task, assignee=self.other, actor=self.member)

    def test_assignee_can_change_status(self):
        task = create_task(
            project=self.project,
            title="Implement endpoint",
            description="",
            priority="medium",
            due_date=None,
            assignee=None,
            created_by=self.member,
        )
        task = assign_task(task=task, assignee=self.member, actor=self.admin)
        updated_task = change_task_status(task=task, status=TaskStatus.DONE, actor=self.member)

        self.assertEqual(updated_task.status, TaskStatus.DONE)

    def test_non_assignee_member_cannot_change_status(self):
        task = create_task(
            project=self.project,
            title="Implement endpoint",
            description="",
            priority="medium",
            due_date=None,
            assignee=None,
            created_by=self.member,
        )
        task = assign_task(task=task, assignee=self.member, actor=self.admin)

        with self.assertRaises(DomainError):
            change_task_status(task=task, status=TaskStatus.DONE, actor=self.other)

    def test_task_edit_view_updates_all_general_fields(self):
        task = create_task(
            project=self.project,
            title="Implement endpoint",
            description="Initial description",
            priority="medium",
            due_date=None,
            assignee=None,
            created_by=self.member,
        )
        self.client.login(username="member", password="secret123")

        response = self.client.post(
            f"/workspaces/{self.workspace.slug}/projects/{self.project.slug}/tasks/{task.slug}/edit/",
            {
                "title": "Updated endpoint",
                "description": "Expanded description",
                "priority": "high",
                "due_date": "2026-06-30",
                "status": task.status,
                "assignee": "",
            },
        )

        if response.status_code != 302:
            print(
                "FORM_ERRORS:",
                response.context["form"].errors,
                "INLINE_ERRORS:",
                [f.errors for f in response.context["inline_admin_formsets"][0].formset.forms],
            )
        self.assertEqual(response.status_code, 302)
        task.refresh_from_db()
        self.assertEqual(task.title, "Updated endpoint")
        self.assertEqual(task.description, "Expanded description")
        self.assertEqual(task.priority, "high")
        self.assertEqual(str(task.due_date), "2026-06-30")

    def test_cannot_create_task_in_archived_project(self):
        archive_project(project=self.project, actor=self.owner)

        with self.assertRaises(DomainError):
            create_task(
                project=self.project,
                title="Blocked task",
                description="",
                priority="medium",
                due_date=None,
                assignee=None,
                created_by=self.member,
            )

    def test_cannot_update_task_in_archived_project(self):
        task = create_task(
            project=self.project,
            title="Implement endpoint",
            description="Initial description",
            priority="medium",
            due_date=None,
            assignee=None,
            created_by=self.member,
        )
        archive_project(project=self.project, actor=self.owner)

        with self.assertRaises(DomainError):
            assign_task(task=task, assignee=self.admin, actor=self.admin)

    def test_task_edit_view_rejects_archived_project(self):
        task = create_task(
            project=self.project,
            title="Implement endpoint",
            description="Initial description",
            priority="medium",
            due_date=None,
            assignee=None,
            created_by=self.member,
        )
        archive_project(project=self.project, actor=self.owner)
        self.client.login(username="member", password="secret123")

        response = self.client.get(
            f"/workspaces/{self.workspace.slug}/projects/{self.project.slug}/tasks/{task.slug}/edit/"
        )

        self.assertEqual(response.status_code, 403)

    def test_admin_can_bulk_assign_and_close_tasks(self):
        first_task = create_task(
            project=self.project,
            title="First task",
            description="",
            priority="medium",
            due_date=None,
            assignee=None,
            created_by=self.member,
        )
        second_task = create_task(
            project=self.project,
            title="Second task",
            description="",
            priority="medium",
            due_date=None,
            assignee=None,
            created_by=self.member,
        )

        updated_tasks = bulk_update_tasks(
            tasks=[first_task, second_task],
            actor=self.admin,
            assignee=self.other,
            status=TaskStatus.DONE,
        )

        self.assertEqual(len(updated_tasks), 2)
        first_task.refresh_from_db()
        second_task.refresh_from_db()
        self.assertEqual(first_task.assignee, self.other)
        self.assertEqual(second_task.assignee, self.other)
        self.assertEqual(first_task.status, TaskStatus.DONE)
        self.assertEqual(second_task.status, TaskStatus.DONE)

    def test_member_bulk_update_rolls_back_when_assignment_is_forbidden(self):
        first_task = create_task(
            project=self.project,
            title="First task",
            description="Original first",
            priority="medium",
            due_date=None,
            assignee=None,
            created_by=self.member,
        )
        second_task = create_task(
            project=self.project,
            title="Second task",
            description="Original second",
            priority="medium",
            due_date=None,
            assignee=None,
            created_by=self.member,
        )

        with self.assertRaises(DomainError):
            bulk_update_tasks(
                tasks=[first_task, second_task],
                actor=self.member,
                description="Blocked bulk update",
                assignee=self.other,
            )

        first_task.refresh_from_db()
        second_task.refresh_from_db()
        self.assertEqual(first_task.description, "Original first")
        self.assertEqual(second_task.description, "Original second")
        self.assertIsNone(first_task.assignee)
        self.assertIsNone(second_task.assignee)


class ProjectTaskListViewPaginationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="list_owner", password="password123")
        self.workspace = create_workspace(owner=self.owner, name="List Workspace")
        self.project = create_project(
            workspace=self.workspace,
            name="List Project",
            description="",
            created_by=self.owner,
        )
        for i in range(25):
            create_task(
                project=self.project,
                title=f"Task {i + 1}",
                description="",
                priority="medium",
                due_date=None,
                assignee=None,
                created_by=self.owner,
            )

    def test_task_list_pagination(self):
        from django.urls import reverse

        self.client.force_login(self.owner)
        url = reverse(
            "project-task-list",
            kwargs={
                "workspace_slug": self.workspace.slug,
                "project_slug": self.project.slug,
            },
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["is_paginated"])
        self.assertEqual(len(response.context["tasks"]), 20)

        response_p2 = self.client.get(url + "?page=2")
        self.assertEqual(response_p2.status_code, 200)
        self.assertEqual(len(response_p2.context["tasks"]), 5)


class TaskTagServiceAndSelectorTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="tag_owner", password="secret123")
        self.admin = User.objects.create_user(username="tag_admin", password="secret123")
        self.member = User.objects.create_user(username="tag_member", password="secret123")
        self.outsider = User.objects.create_user(username="tag_outsider", password="secret123")

        self.workspace = create_workspace(owner=self.owner, name="Tag WS")
        Membership.objects.create(
            workspace=self.workspace, user=self.admin, role=MembershipRole.ADMIN
        )
        Membership.objects.create(
            workspace=self.workspace, user=self.member, role=MembershipRole.MEMBER
        )

        self.other_workspace = create_workspace(owner=self.outsider, name="Other WS")

    def test_owner_and_admin_can_create_tag(self):
        tag1 = create_task_tag(
            workspace=self.workspace, name="Bug", color="#ff0000", actor=self.owner
        )
        self.assertEqual(tag1.name, "Bug")
        self.assertEqual(tag1.slug, "bug")
        self.assertEqual(tag1.color, "#ff0000")

        tag2 = create_task_tag(
            workspace=self.workspace, name="Feature", color="#00ff00", actor=self.admin
        )
        self.assertEqual(tag2.name, "Feature")
        self.assertEqual(tag2.slug, "feature")

    def test_member_and_outsider_cannot_create_tag(self):
        with self.assertRaises(DomainError):
            create_task_tag(workspace=self.workspace, name="Docs", actor=self.member)

        with self.assertRaises(DomainError):
            create_task_tag(workspace=self.workspace, name="Docs", actor=self.outsider)

    def test_tag_name_case_insensitive_unique_within_workspace(self):
        create_task_tag(workspace=self.workspace, name="Frontend", actor=self.owner)
        with self.assertRaises(DomainError):
            create_task_tag(workspace=self.workspace, name="frontend", actor=self.owner)

    def test_same_tag_name_allowed_in_different_workspaces(self):
        tag1 = create_task_tag(workspace=self.workspace, name="Design", actor=self.owner)
        tag2 = create_task_tag(workspace=self.other_workspace, name="Design", actor=self.outsider)
        self.assertEqual(tag1.name, tag2.name)
        self.assertNotEqual(tag1.workspace, tag2.workspace)

    def test_hex_color_validation(self):
        with self.assertRaises(DomainError):
            create_task_tag(
                workspace=self.workspace, name="BadColor", color="not-a-color", actor=self.owner
            )

        with self.assertRaises(DomainError):
            create_task_tag(
                workspace=self.workspace, name="BadHex", color="#gggggg", actor=self.owner
            )

        tag = create_task_tag(
            workspace=self.workspace, name="ValidHex", color="#ABC", actor=self.owner
        )
        self.assertEqual(tag.color, "#abc")

    def test_update_and_delete_tag(self):
        tag = create_task_tag(
            workspace=self.workspace, name="Initial", color="#111111", actor=self.owner
        )
        updated = update_task_tag(tag=tag, actor=self.admin, name="Renamed", color="#222222")
        self.assertEqual(updated.name, "Renamed")
        self.assertEqual(updated.color, "#222222")

        delete_task_tag(tag=updated, actor=self.admin)
        self.assertEqual(TaskTag.objects.filter(id=tag.id).count(), 0)

    def test_tag_selectors(self):
        t1 = create_task_tag(workspace=self.workspace, name="Alpha", actor=self.owner)
        t2 = create_task_tag(workspace=self.workspace, name="Beta", actor=self.owner)

        tags = list(get_workspace_tags(workspace=self.workspace))
        self.assertEqual(tags, [t1, t2])
        self.assertEqual(get_workspace_tag_by_slug(workspace=self.workspace, slug="alpha"), t1)
        self.assertEqual(get_workspace_tag_by_id(workspace=self.workspace, tag_id=t2.id), t2)


class TaskTagAssignmentTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="assign_owner", password="secret123")
        self.member = User.objects.create_user(username="assign_member", password="secret123")
        self.outsider = User.objects.create_user(username="assign_outsider", password="secret123")

        self.workspace = create_workspace(owner=self.owner, name="Tag Assignment WS")
        Membership.objects.create(
            workspace=self.workspace, user=self.member, role=MembershipRole.MEMBER
        )
        self.project = create_project(
            workspace=self.workspace, name="Main", description="", created_by=self.owner
        )
        self.task = create_task(
            project=self.project,
            title="Tagged Task",
            description="",
            priority="medium",
            due_date=None,
            assignee=None,
            created_by=self.member,
        )

        self.other_ws = create_workspace(owner=self.outsider, name="Other WS")
        self.foreign_tag = create_task_tag(
            workspace=self.other_ws, name="Foreign", actor=self.outsider
        )
        self.tag1 = create_task_tag(workspace=self.workspace, name="Tag1", actor=self.owner)
        self.tag2 = create_task_tag(workspace=self.workspace, name="Tag2", actor=self.owner)

    def test_member_can_assign_and_remove_tag(self):
        assign_tag_to_task(task=self.task, tag=self.tag1, actor=self.member)
        self.assertIn(self.tag1, self.task.tags.all())

        set_task_tags(task=self.task, tags=[self.tag1, self.tag2], actor=self.member)
        self.assertEqual(set(self.task.tags.all()), {self.tag1, self.tag2})

        remove_tag_from_task(task=self.task, tag=self.tag1, actor=self.member)
        self.assertEqual(list(self.task.tags.all()), [self.tag2])

    def test_cannot_assign_foreign_workspace_tag(self):
        with self.assertRaises(DomainError):
            assign_tag_to_task(task=self.task, tag=self.foreign_tag, actor=self.member)

        with self.assertRaises(DomainError):
            set_task_tags(task=self.task, tags=[self.tag1, self.foreign_tag], actor=self.member)

        with self.assertRaises(DomainError):
            create_task(
                project=self.project,
                title="Cross-tagged Task",
                description="",
                priority="low",
                due_date=None,
                assignee=None,
                created_by=self.member,
                tags=[self.foreign_tag],
            )


class TaskChecklistServiceAndSelectorTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="cl_owner", password="secret123")
        self.member = User.objects.create_user(username="cl_member", password="secret123")
        self.outsider = User.objects.create_user(username="cl_outsider", password="secret123")

        self.workspace = create_workspace(owner=self.owner, name="Checklist WS")
        Membership.objects.create(
            workspace=self.workspace, user=self.member, role=MembershipRole.MEMBER
        )
        self.project = create_project(
            workspace=self.workspace, name="Dev", description="", created_by=self.owner
        )
        self.task = create_task(
            project=self.project,
            title="Checklist Task",
            description="",
            priority="medium",
            due_date=None,
            assignee=None,
            created_by=self.member,
        )

    def test_add_and_toggle_checklist_item(self):
        item = add_checklist_item(task=self.task, text="Write migrations", actor=self.member)
        self.assertEqual(item.text, "Write migrations")
        self.assertFalse(item.is_completed)
        self.assertEqual(item.position, 0)

        toggled = toggle_checklist_item(item=item, actor=self.member)
        self.assertTrue(toggled.is_completed)

        update_checklist_item(item=item, actor=self.member, text="Updated text", is_completed=False)
        item.refresh_from_db()
        self.assertEqual(item.text, "Updated text")
        self.assertFalse(item.is_completed)

    def test_empty_checklist_item_text_rejected(self):
        with self.assertRaises(DomainError):
            add_checklist_item(task=self.task, text="   ", actor=self.member)

    def test_outsider_cannot_modify_checklist(self):
        with self.assertRaises(DomainError):
            add_checklist_item(task=self.task, text="Hacked item", actor=self.outsider)

    def test_delete_checklist_item_renormalizes_positions(self):
        item1 = add_checklist_item(task=self.task, text="Item 1", actor=self.member)
        item2 = add_checklist_item(task=self.task, text="Item 2", actor=self.member)
        item3 = add_checklist_item(task=self.task, text="Item 3", actor=self.member)

        delete_checklist_item(item=item2, actor=self.member)
        items = list(get_task_checklist_items(task=self.task))
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].id, item1.id)
        self.assertEqual(items[0].position, 0)
        self.assertEqual(items[1].id, item3.id)
        self.assertEqual(items[1].position, 1)

    def test_reorder_checklist_items(self):
        item1 = add_checklist_item(task=self.task, text="Step 1", actor=self.member)
        item2 = add_checklist_item(task=self.task, text="Step 2", actor=self.member)
        item3 = add_checklist_item(task=self.task, text="Step 3", actor=self.member)

        reordered = reorder_checklist_items(
            task=self.task, item_ids=[item3.id, item1.id, item2.id], actor=self.member
        )
        self.assertEqual([i.id for i in reordered], [item3.id, item1.id, item2.id])
        self.assertEqual([i.position for i in reordered], [0, 1, 2])

    def test_invalid_reorder_rejected(self):
        item1 = add_checklist_item(task=self.task, text="Step 1", actor=self.member)
        add_checklist_item(task=self.task, text="Step 2", actor=self.member)

        with self.assertRaises(DomainError):
            reorder_checklist_items(task=self.task, item_ids=[item1.id, 9999], actor=self.member)


class TaskLifecycleAndArchivalTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="life_owner", password="secret123")
        self.admin = User.objects.create_user(username="life_admin", password="secret123")
        self.member = User.objects.create_user(username="life_member", password="secret123")
        self.outsider = User.objects.create_user(username="life_outsider", password="secret123")

        self.workspace = create_workspace(owner=self.owner, name="Lifecycle WS")
        Membership.objects.create(
            workspace=self.workspace, user=self.admin, role=MembershipRole.ADMIN
        )
        Membership.objects.create(
            workspace=self.workspace, user=self.member, role=MembershipRole.MEMBER
        )
        self.project = create_project(
            workspace=self.workspace, name="Prod", description="", created_by=self.owner
        )
        self.task = create_task(
            project=self.project,
            title="Lifecycle Task",
            description="",
            priority="medium",
            due_date=None,
            assignee=None,
            created_by=self.member,
        )

    def test_archive_and_restore_task(self):
        archived = archive_task(task=self.task, actor=self.member)
        self.assertTrue(archived.is_archived)

        with self.assertRaises(DomainError):
            change_task_status(task=archived, status="done", actor=self.owner)

        restored = restore_task(task=archived, actor=self.admin)
        self.assertFalse(restored.is_archived)

    def test_cannot_modify_tasks_in_archived_project(self):
        archive_project(project=self.project, actor=self.owner)

        with self.assertRaises(DomainError):
            archive_task(task=self.task, actor=self.owner)

        with self.assertRaises(DomainError):
            create_task(
                project=self.project,
                title="New Task in Archived Project",
                description="",
                priority="low",
                due_date=None,
                assignee=None,
                created_by=self.member,
            )


class TaskDeletionAndAuditTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="del_owner", password="secret123")
        self.admin = User.objects.create_user(username="del_admin", password="secret123")
        self.member = User.objects.create_user(username="del_member", password="secret123")
        self.other_member = User.objects.create_user(username="del_other", password="secret123")

        self.workspace = create_workspace(owner=self.owner, name="Deletion WS")
        Membership.objects.create(
            workspace=self.workspace, user=self.admin, role=MembershipRole.ADMIN
        )
        Membership.objects.create(
            workspace=self.workspace, user=self.member, role=MembershipRole.MEMBER
        )
        Membership.objects.create(
            workspace=self.workspace, user=self.other_member, role=MembershipRole.MEMBER
        )
        self.project = create_project(
            workspace=self.workspace, name="Del Project", description="", created_by=self.owner
        )
        self.task = create_task(
            project=self.project,
            title="Task to delete",
            description="Detailed description",
            priority="high",
            due_date=None,
            assignee=None,
            created_by=self.member,
        )
        self.comment = add_comment(task=self.task, author=self.member, text="A comment")
        self.item = add_checklist_item(task=self.task, text="Item to delete", actor=self.member)

    def test_random_member_cannot_delete_task(self):
        with self.assertRaises(DomainError):
            delete_task(task=self.task, actor=self.other_member)

    def test_creator_can_delete_task_with_cascade_and_audit_preservation(self):
        task_id = self.task.id
        delete_task(task=self.task, actor=self.member)

        self.assertEqual(Task.objects.filter(id=task_id).count(), 0)
        self.assertEqual(Comment.objects.filter(id=self.comment.id).count(), 0)
        self.assertEqual(TaskChecklistItem.objects.filter(id=self.item.id).count(), 0)

        logs = ActivityLog.objects.filter(
            workspace=self.workspace, target_type="task", target_id=str(task_id)
        )
        self.assertTrue(logs.filter(action="task_created").exists())
        self.assertTrue(logs.filter(action="task_deleted").exists())
        del_log = logs.get(action="task_deleted")
        self.assertEqual(del_log.metadata["task_title"], "Task to delete")
        self.assertEqual(del_log.metadata["comments_deleted"], 1)
        self.assertEqual(del_log.metadata["checklist_items_deleted"], 1)

    def test_admin_can_delete_task(self):
        delete_task(task=self.task, actor=self.admin)
        self.assertEqual(Task.objects.filter(id=self.task.id).count(), 0)


class TaskIntegrityCheckTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="integ_owner", password="secret123")
        self.workspace1 = create_workspace(owner=self.owner, name="Integ 1")
        self.workspace2 = create_workspace(owner=self.owner, name="Integ 2")
        self.project = create_project(
            workspace=self.workspace1, name="Integ Proj", description="", created_by=self.owner
        )
        self.task = create_task(
            project=self.project,
            title="Integ Task",
            description="",
            priority="low",
            due_date=None,
            assignee=None,
            created_by=self.owner,
        )

    def test_integrity_detects_cross_workspace_tag(self):
        tag_ws2 = TaskTag.objects.create(
            workspace=self.workspace2, name="CrossTag", slug="cross-tag"
        )
        self.task.tags.add(tag_ws2)

        issues = check_task_tag_workspace_integrity()
        self.assertTrue(any("CrossTag" in issue or "cross-tag" in issue for issue in issues))

    def test_integrity_detects_empty_checklist_item(self):
        item = TaskChecklistItem.objects.create(task=self.task, text="", position=0)
        issues = check_checklist_item_integrity()
        self.assertTrue(any(str(item.id) in issue for issue in issues))


class TaskPermissionTrapTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="trap_owner", password="secret123")
        self.workspace = create_workspace(owner=self.owner, name="Trap WS")
        self.project = create_project(
            workspace=self.workspace, name="Trap Project", description="", created_by=self.owner
        )
        self.task = create_task(
            project=self.project,
            title="Unassigned Task",
            description="",
            priority="low",
            due_date=None,
            assignee=None,
            created_by=self.owner,
        )
        self.comment = add_comment(task=self.task, author=self.owner, text="Trap comment")

    def test_anonymous_and_none_user_cannot_bypass_permissions(self):
        from django.contrib.auth.models import AnonymousUser

        from core.permissions import (
            can_archive_task,
            can_change_task_status,
            can_delete_comment,
            can_delete_task,
        )

        anon = AnonymousUser()

        class FakeUserWithNoneId:
            id = None
            is_authenticated = False

        fake_user = FakeUserWithNoneId()

        for user in [anon, fake_user, None]:
            self.assertFalse(can_change_task_status(task=self.task, user=user))
            self.assertFalse(can_archive_task(task=self.task, user=user))
            self.assertFalse(can_delete_task(task=self.task, user=user))
            self.assertFalse(can_delete_comment(comment=self.comment, user=user))


class TaskTagCaseInsensitiveConstraintTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="tag_ci_owner", password="secret123")
        self.workspace = create_workspace(owner=self.owner, name="Tag CI WS")

    def test_tag_name_case_insensitive_duplicate_rejected(self):
        from django.db import IntegrityError

        create_task_tag(workspace=self.workspace, name="Backend", actor=self.owner)

        # Service level should catch and raise DomainError
        with self.assertRaises(DomainError):
            create_task_tag(workspace=self.workspace, name="backend", actor=self.owner)

        with self.assertRaises(DomainError):
            create_task_tag(workspace=self.workspace, name="BACKEND", actor=self.owner)

        # Direct DB level should raise IntegrityError
        with self.assertRaises(IntegrityError):
            TaskTag.objects.create(workspace=self.workspace, name="backend", slug="backend-2")

    def test_update_tag_name_case_insensitive_duplicate_rejected(self):
        create_task_tag(workspace=self.workspace, name="Frontend", actor=self.owner)
        tag2 = create_task_tag(workspace=self.workspace, name="DevOps", actor=self.owner)

        with self.assertRaises(DomainError):
            update_task_tag(tag=tag2, actor=self.owner, name="frontend")


class TaskAdminTagValidationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="adm_owner", password="secret123")
        self.workspace1 = create_workspace(owner=self.owner, name="Admin WS 1")
        self.workspace2 = create_workspace(owner=self.owner, name="Admin WS 2")
        self.project1 = create_project(
            workspace=self.workspace1, name="Admin Proj 1", description="", created_by=self.owner
        )
        self.task1 = create_task(
            project=self.project1,
            title="Admin Task",
            description="",
            priority="low",
            due_date=None,
            assignee=None,
            created_by=self.owner,
        )
        self.tag_ws1 = create_task_tag(
            workspace=self.workspace1, name="WS1 Tag", actor=self.owner
        )
        self.tag_ws2 = create_task_tag(
            workspace=self.workspace2, name="WS2 Tag", actor=self.owner
        )

    def test_task_admin_form_rejects_cross_workspace_tag(self):
        from tasks.admin import TaskAdminForm

        form = TaskAdminForm(
            instance=self.task1,
            data={
                "project": self.project1.id,
                "title": "Admin Task",
                "priority": "low",
                "status": "todo",
                "tags": [self.tag_ws2.id],
            },
        )
        self.assertFalse(form.is_valid())
        self.assertIn("tags", form.errors)
        self.assertTrue(
            any("Tags do not belong to the task workspace" in err for err in form.errors["tags"])
        )

    def test_add_checklist_item_with_is_completed(self):
        item = add_checklist_item(
            task=self.task1, text="Completed upfront", actor=self.owner, is_completed=True
        )
        self.assertTrue(item.is_completed)

    def test_task_tag_admin_lifecycle(self):
        from django.contrib.admin.sites import AdminSite

        from tasks.admin import TaskTagAdmin

        admin_site = AdminSite()
        tag_admin = TaskTagAdmin(TaskTag, admin_site)

        # Mock request with user
        class DummyRequest:
            user = self.owner

        req = DummyRequest()
        new_tag = TaskTag(workspace=self.workspace1, name="DevAdmin", color="#112233")
        tag_admin.save_model(req, new_tag, None, change=False)

        self.assertIsNotNone(new_tag.id)
        self.assertEqual(new_tag.slug, "devadmin")
        self.assertEqual(new_tag.name, "DevAdmin")

        # Test delete via admin
        tag_admin.delete_model(req, new_tag)
        self.assertEqual(TaskTag.objects.filter(name="DevAdmin").count(), 0)

    def test_create_with_unique_slug_savepoint_safety_under_atomic(self):
        from django.db import transaction

        from core.slugs import create_with_unique_slug

        # Create tag with slug "qa"
        create_task_tag(workspace=self.workspace1, name="qa", actor=self.owner)

        with transaction.atomic():
            tag2 = create_with_unique_slug(
                model=TaskTag,
                value="qa",
                scope={"workspace": self.workspace1},
                create_kwargs={"workspace": self.workspace1, "name": "qa2", "color": "#000000"},
            )
            self.assertEqual(tag2.slug, "qa-2")


class DjangoAdminIntegrationTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username="admin_super", email="admin@example.com", password="superpass123"
        )
        self.workspace = create_workspace(owner=self.superuser, name="Admin WS")
        self.other_workspace = create_workspace(owner=self.superuser, name="Other WS")
        self.project = create_project(
            workspace=self.workspace, name="Main Project", description="", created_by=self.superuser
        )
        self.tag = create_task_tag(
            workspace=self.workspace, name="Design", color="#ff0000", actor=self.superuser
        )
        self.task = create_task(
            project=self.project,
            title="Admin Main Task",
            description="Initial desc",
            priority="medium",
            due_date=None,
            assignee=None,
            created_by=self.superuser,
            tags=[self.tag],
        )
        self.item = add_checklist_item(
            task=self.task, text="Initial step", actor=self.superuser, is_completed=False
        )
        self.client.login(username="admin_super", password="superpass123")

    def test_admin_change_tag_name_and_color(self):
        url = f"/admin/tasks/tasktag/{self.tag.id}/change/"
        response = self.client.post(
            url,
            {
                "workspace": self.workspace.id,
                "name": "Design Updated",
                "color": "#00ff00",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.tag.refresh_from_db()
        self.assertEqual(self.tag.name, "Design Updated")
        self.assertEqual(self.tag.color, "#00ff00")

        # Verify ActivityLog created
        self.assertTrue(
            ActivityLog.objects.filter(
                workspace=self.workspace,
                action="tag_updated",
                metadata__tag_name="Design Updated",
                metadata__tag_color="#00ff00",
            ).exists()
        )

    def test_admin_tag_moving_to_other_workspace_forbidden(self):
        from tasks.admin import TaskTagAdminForm

        # 1. Form-level rejection
        form = TaskTagAdminForm(
            instance=self.tag,
            data={"workspace": self.other_workspace.id, "name": "Design", "color": "#ff0000"},
        )
        self.assertFalse(form.is_valid())
        self.assertIn("workspace", form.errors)
        self.assertIn(
            "Moving a tag to a different workspace is not allowed.", form.errors["workspace"]
        )

        # 2. HTTP post to admin cannot change workspace (it is readonly)
        url = f"/admin/tasks/tasktag/{self.tag.id}/change/"
        response = self.client.post(
            url,
            {
                "workspace": self.other_workspace.id,
                "name": "Design Name",
                "color": "#ff0000",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.tag.refresh_from_db()
        self.assertEqual(self.tag.workspace_id, self.workspace.id)

    def test_admin_change_checklist_item_text_and_is_completed(self):
        url = f"/admin/tasks/taskchecklistitem/{self.item.id}/change/"
        response = self.client.post(
            url,
            {
                "task": self.task.id,
                "text": "Item Revised Text",
                "is_completed": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.item.refresh_from_db()
        self.assertEqual(self.item.text, "Item Revised Text")
        self.assertTrue(self.item.is_completed)

        self.assertTrue(
            ActivityLog.objects.filter(
                workspace=self.workspace,
                action="checklist_item_updated",
                metadata__item_id=self.item.id,
                metadata__text="Item Revised Text",
                metadata__is_completed=True,
            ).exists()
        )

    def test_admin_checklist_item_moving_to_other_task_forbidden(self):
        from tasks.admin import TaskChecklistItemAdminForm

        task2 = create_task(
            project=self.project,
            title="Second Task",
            description="",
            priority="low",
            due_date=None,
            assignee=None,
            created_by=self.superuser,
        )
        # 1. Form-level rejection
        form = TaskChecklistItemAdminForm(
            instance=self.item,
            data={"task": task2.id, "text": "Step", "is_completed": False},
        )
        self.assertFalse(form.is_valid())
        self.assertIn("task", form.errors)
        self.assertIn(
            "Moving a checklist item to a different task is not allowed.", form.errors["task"]
        )

        # 2. HTTP post to admin cannot change task (it is readonly)
        url = f"/admin/tasks/taskchecklistitem/{self.item.id}/change/"
        response = self.client.post(
            url,
            {
                "task": task2.id,
                "text": "Item Move Attempt",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.item.refresh_from_db()
        self.assertEqual(self.item.task_id, self.task.id)

    def test_admin_task_archive_and_restore_actions(self):
        list_url = "/admin/tasks/task/"
        # Archive
        arc_res = self.client.post(
            list_url,
            {
                "action": "archive_selected_tasks",
                "_selected_action": [str(self.task.id)],
            },
        )
        self.assertEqual(arc_res.status_code, 302)
        self.task.refresh_from_db()
        self.assertTrue(self.task.is_archived)
        self.assertTrue(
            ActivityLog.objects.filter(
                workspace=self.workspace,
                action="task_archived",
                target_id=str(self.task.id),
            ).exists()
        )

        # Restore
        res_res = self.client.post(
            list_url,
            {
                "action": "restore_selected_tasks",
                "_selected_action": [str(self.task.id)],
            },
        )
        self.assertEqual(res_res.status_code, 302)
        self.task.refresh_from_db()
        self.assertFalse(self.task.is_archived)
        self.assertTrue(
            ActivityLog.objects.filter(
                workspace=self.workspace,
                action="task_restored",
                target_id=str(self.task.id),
            ).exists()
        )

    def test_admin_edit_archived_task_rejected(self):
        archive_task(task=self.task, actor=self.superuser)
        url = f"/admin/tasks/task/{self.task.id}/change/"
        response = self.client.post(
            url,
            {
                "project": self.project.id,
                "title": "Edited while archived",
                "priority": "low",
                "status": "todo",
                "tags": [self.tag.id],
                "checklist_items-TOTAL_FORMS": "1",
                "checklist_items-INITIAL_FORMS": "1",
                "checklist_items-MIN_NUM_FORMS": "0",
                "checklist_items-MAX_NUM_FORMS": "1000",
                "checklist_items-0-id": str(self.item.id),
                "checklist_items-0-task": str(self.task.id),
                "checklist_items-0-text": self.item.text,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            any(
                "Archived tasks cannot be edited" in str(err)
                for err in response.context["errors"]
            )
        )
        self.task.refresh_from_db()
        self.assertEqual(self.task.title, "Admin Main Task")

    def test_admin_task_change_tags_no_duplicate_activity_log(self):
        initial_count = ActivityLog.objects.filter(action="task_tags_updated").count()
        tag2 = create_task_tag(
            workspace=self.workspace, name="UI", color="#333333", actor=self.superuser
        )
        url = f"/admin/tasks/task/{self.task.id}/change/"
        response = self.client.post(
            url,
            {
                "project": self.project.id,
                "title": self.task.title,
                "priority": self.task.priority,
                "status": self.task.status,
                "tags": [self.tag.id, tag2.id],
                "checklist_items-TOTAL_FORMS": "1",
                "checklist_items-INITIAL_FORMS": "1",
                "checklist_items-MIN_NUM_FORMS": "0",
                "checklist_items-MAX_NUM_FORMS": "1000",
                "checklist_items-0-id": str(self.item.id),
                "checklist_items-0-task": str(self.task.id),
                "checklist_items-0-text": self.item.text,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.task.refresh_from_db()
        self.assertEqual(set(self.task.tags.all()), {self.tag, tag2})
        # Exactly one activity log event generated
        self.assertEqual(
            ActivityLog.objects.filter(action="task_tags_updated").count(),
            initial_count + 1,
        )

    def test_admin_task_change_with_cross_workspace_tag_atomic_rollback(self):
        foreign_tag = create_task_tag(
            workspace=self.other_workspace,
            name="ForeignTag",
            color="#999999",
            actor=self.superuser,
        )
        orig_title = self.task.title
        url = f"/admin/tasks/task/{self.task.id}/change/"
        response = self.client.post(
            url,
            {
                "project": self.project.id,
                "title": "New Title That Should Roll Back",
                "priority": "low",
                "status": "todo",
                "tags": [foreign_tag.id],
                "checklist_items-TOTAL_FORMS": "1",
                "checklist_items-INITIAL_FORMS": "1",
                "checklist_items-MIN_NUM_FORMS": "0",
                "checklist_items-MAX_NUM_FORMS": "1000",
                "checklist_items-0-id": str(self.item.id),
                "checklist_items-0-task": str(self.task.id),
                "checklist_items-0-text": self.item.text,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.title, orig_title)
        self.assertEqual(list(self.task.tags.all()), [self.tag])



