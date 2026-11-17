import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.generic import FormView, TemplateView, View

from comments.forms import CommentForm
from comments.selectors import get_task_comments
from core.exceptions import DomainError
from core.permissions import (
    can_assign_task,
    can_change_task_status,
    can_create_task,
    get_workspace_membership,
    has_membership_role,
)
from projects.models import Project
from projects.selectors import get_workspace_project_by_slug
from tasks.forms import TaskCreateForm, TaskUpdateForm
from tasks.models import Task, TaskPriority, TaskStatus
from tasks.selectors import (
    filter_tasks,
    get_kanban_board_tasks,
    get_kanban_column_page,
    get_project_task_by_slug,
    get_project_task_candidates,
    get_project_tasks,
    get_workspace_tags,
)
from tasks.services import change_task_status, create_task, update_task


class ProjectTaskAccessMixin(LoginRequiredMixin):
    project = None

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            if request.headers.get("X-TTM-Kanban-Drag") == "true":
                return HttpResponse("Authentication required.", status=401)
            return self.handle_no_permission()
        try:
            self.project = get_workspace_project_by_slug(
                workspace_slug=kwargs["workspace_slug"],
                project_slug=kwargs["project_slug"],
                user=request.user,
            )
        except Project.DoesNotExist as exc:
            raise Http404("Project not found.") from exc
        return super().dispatch(request, *args, **kwargs)


class TaskAccessMixin(LoginRequiredMixin):
    task = None
    allow_archived = True

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            if request.headers.get("X-TTM-Kanban-Drag") == "true":
                return HttpResponse("Authentication required.", status=401)
            return self.handle_no_permission()
        try:
            self.task = get_project_task_by_slug(
                workspace_slug=kwargs["workspace_slug"],
                project_slug=kwargs["project_slug"],
                task_slug=kwargs["task_slug"],
                user=request.user,
            )
        except Task.DoesNotExist as exc:
            raise Http404("Task not found.") from exc
        if not self.allow_archived and self.task.project.is_archived:
            raise PermissionDenied("Archived projects are read-only.")
        return super().dispatch(request, *args, **kwargs)


class ProjectTaskListView(ProjectTaskAccessMixin, FormView):
    form_class = TaskCreateForm
    template_name = "tasks/task_list.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["members"] = get_project_task_candidates(project=self.project)
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        is_cleared = self.request.GET.get("clear") == "1"
        if is_cleared:
            search = None
            status_val = None
            priority = None
            assignee_id = None
            tag_slug = None
            is_overdue = None
            is_archived = False
            archived_param = "0"
        else:
            search = self.request.GET.get("search", "").strip() or None
            status_val = self.request.GET.get("status", "").strip() or None
            priority = self.request.GET.get("priority", "").strip() or None
            assignee_id = self.request.GET.get("assignee", "").strip() or None
            tag_slug = self.request.GET.get("tag", "").strip() or None
            is_overdue = self.request.GET.get("is_overdue", "").strip() or None
            archived_param = self.request.GET.get("is_archived", "").strip()

            if archived_param in ("1", "true"):
                is_archived = True
            elif archived_param == "all":
                is_archived = None
            else:
                is_archived = False
                archived_param = "0"

        tasks_qs = get_project_tasks(project=self.project)
        try:
            tasks_qs = filter_tasks(
                tasks_qs,
                status_value=status_val,
                priority=priority,
                assignee_id=assignee_id,
                tag_slug=tag_slug,
                is_overdue=is_overdue,
                is_archived=is_archived,
                search=search,
            )
        except ValueError:
            tasks_qs = filter_tasks(tasks_qs, is_archived=is_archived)

        paginator = Paginator(tasks_qs, 20)
        page_obj = paginator.get_page(self.request.GET.get("page"))

        try:
            kanban_board = get_kanban_board_tasks(
                project=self.project,
                per_column_limit=20,
                status_value=status_val,
                priority=priority,
                assignee_id=assignee_id,
                tag_slug=tag_slug,
                is_overdue=is_overdue,
                is_archived=is_archived,
                search=search,
            )
        except ValueError:
            kanban_board = get_kanban_board_tasks(
                project=self.project,
                per_column_limit=20,
                is_archived=is_archived,
            )

        membership = get_workspace_membership(
            workspace=self.project.workspace,
            user=self.request.user,
        )
        is_workspace_admin = has_membership_role(membership, "owner", "admin")

        context["project"] = self.project
        context["tasks"] = page_obj
        context["kanban_board"] = kanban_board
        context["page_obj"] = page_obj
        context["is_paginated"] = page_obj.has_other_pages()
        context["can_create_task"] = can_create_task(project=self.project, user=self.request.user)
        context["is_project_archived"] = self.project.is_archived
        context["is_workspace_admin"] = is_workspace_admin
        context["can_change_task_status"] = is_workspace_admin
        context["project_tags"] = get_workspace_tags(workspace=self.project.workspace)
        context["members"] = get_project_task_candidates(project=self.project)
        context["current_filters"] = {
            "search": search or "",
            "status": status_val or "",
            "priority": priority or "",
            "assignee": assignee_id or "",
            "tag": tag_slug or "",
            "is_overdue": is_overdue or "",
            "is_archived": archived_param or "0",
        }
        context["htmx_target"] = "#tasks-view-container"
        context["is_cleared"] = is_cleared
        return context

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get("HX-Request") == "true":
            target = self.request.headers.get("HX-Target")
            if target == "task-list-container":
                template = "tasks/partials/task_list_container.html"
            else:
                template = "tasks/partials/tasks_view_container.html"
            return self.response_class(
                request=self.request,
                template=template,
                context=context,
                using=self.template_engine,
                **response_kwargs,
            )
        return super().render_to_response(context, **response_kwargs)

    def form_valid(self, form):
        if not can_create_task(project=self.project, user=self.request.user):
            raise PermissionDenied("Task creation requires workspace membership.")

        try:
            task = create_task(
                project=self.project,
                title=form.cleaned_data["title"],
                description=form.cleaned_data["description"],
                priority=form.cleaned_data["priority"],
                due_date=form.cleaned_data["due_date"],
                assignee=form.cleaned_data["assignee"],
                created_by=self.request.user,
            )
        except DomainError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)

        messages.success(self.request, "Task created.")
        return redirect(
            "task-detail",
            workspace_slug=task.project.workspace.slug,
            project_slug=task.project.slug,
            task_slug=task.slug,
        )


class TaskDetailView(TaskAccessMixin, TemplateView):
    template_name = "tasks/task_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        comments = list(get_task_comments(task=self.task))
        membership = get_workspace_membership(
            workspace=self.task.project.workspace,
            user=self.request.user,
        )
        is_workspace_admin = has_membership_role(membership, "owner", "admin")
        context["task"] = self.task
        context["comments"] = comments
        context["comment_form"] = (
            None if (self.task.project.is_archived or self.task.is_archived) else CommentForm()
        )
        context["can_edit_task"] = not self.task.project.is_archived and not self.task.is_archived
        context["is_project_archived"] = self.task.project.is_archived
        context["is_workspace_admin"] = is_workspace_admin
        context["can_change_status"] = can_change_task_status(
            task=self.task, user=self.request.user
        )
        context["deletable_comment_ids"] = {
            comment.id
            for comment in comments
            if not self.task.project.is_archived
            and not self.task.is_archived
            and (is_workspace_admin or comment.author_id == self.request.user.id)
        }
        return context


class TaskStatusUpdateView(TaskAccessMixin, View):
    allow_archived = True

    def post(self, request, *args, **kwargs):
        is_htmx = request.headers.get("HX-Request") == "true"
        is_kanban_drag = request.headers.get("X-TTM-Kanban-Drag") == "true"
        new_status = request.POST.get("status")

        if not new_status or new_status not in TaskStatus.values:
            if is_htmx or is_kanban_drag:
                return HttpResponse("Invalid task status.", status=400)
            messages.error(request, "Invalid task status.")
            return redirect(
                "task-detail",
                workspace_slug=self.task.project.workspace.slug,
                project_slug=self.task.project.slug,
                task_slug=self.task.slug,
            )

        if not can_change_task_status(task=self.task, user=request.user):
            if is_htmx or is_kanban_drag:
                return HttpResponse(
                    "Permission denied. Status change requires admin access or assignee role.",
                    status=403,
                )
            raise PermissionDenied(
                "Status change requires admin access or assignee role."
            )

        try:
            self.task = change_task_status(task=self.task, status=new_status, actor=request.user)
        except DomainError as exc:
            if is_htmx or is_kanban_drag:
                return HttpResponse(str(exc), status=400)
            messages.error(request, str(exc))
            return redirect(
                "task-detail",
                workspace_slug=self.task.project.workspace.slug,
                project_slug=self.task.project.slug,
                task_slug=self.task.slug,
            )

        if is_kanban_drag:
            return JsonResponse(
                {
                    "success": True,
                    "task_id": self.task.id,
                    "task_slug": self.task.slug,
                    "status": self.task.status,
                    "status_display": self.task.get_status_display(),
                }
            )

        if is_htmx:
            membership = get_workspace_membership(
                workspace=self.task.project.workspace,
                user=request.user,
            )
            is_workspace_admin = has_membership_role(membership, "owner", "admin")
            response = render(
                request,
                "tasks/partials/task_status_dropdown.html",
                {
                    "task": self.task,
                    "can_change_status": True,
                    "is_workspace_admin": is_workspace_admin,
                },
            )
            response["HX-Trigger"] = "taskStatusChanged"
            return response

        messages.success(request, f"Task status updated to {self.task.get_status_display()}.")
        return redirect(
            "task-detail",
            workspace_slug=self.task.project.workspace.slug,
            project_slug=self.task.project.slug,
            task_slug=self.task.slug,
        )


class KanbanTaskQuickCreateView(ProjectTaskAccessMixin, View):
    def post(self, request, *args, **kwargs):
        is_htmx = request.headers.get("HX-Request") == "true"
        title = request.POST.get("title", "").strip()
        status = request.POST.get("status", TaskStatus.TODO).strip()
        priority = request.POST.get("priority", TaskPriority.MEDIUM).strip()

        if not title:
            if is_htmx:
                return HttpResponse("Task title is required.", status=400)
            messages.error(request, "Task title is required.")
            return redirect(
                "project-task-list",
                workspace_slug=self.project.workspace.slug,
                project_slug=self.project.slug,
            )

        if status not in TaskStatus.values:
            if is_htmx:
                return HttpResponse(f"Invalid task status '{status}'.", status=400)
            messages.error(request, f"Invalid task status '{status}'.")
            return redirect(
                "project-task-list",
                workspace_slug=self.project.workspace.slug,
                project_slug=self.project.slug,
            )

        if priority not in TaskPriority.values:
            priority = TaskPriority.MEDIUM

        if not can_create_task(project=self.project, user=request.user):
            if is_htmx:
                return HttpResponse(
                    "Permission denied. Task creation requires workspace membership.",
                    status=403,
                )
            raise PermissionDenied("Task creation requires workspace membership.")

        membership = get_workspace_membership(
            workspace=self.project.workspace,
            user=request.user,
        )
        is_workspace_admin = has_membership_role(membership, "owner", "admin")

        if status != TaskStatus.TODO and not is_workspace_admin:
            if is_htmx:
                return HttpResponse(
                    "Permission denied. Status change requires admin access or assignee role.",
                    status=403,
                )
            raise PermissionDenied(
                "Status change requires admin access or assignee role."
            )

        try:
            task = create_task(
                project=self.project,
                title=title,
                description="",
                priority=priority,
                due_date=None,
                assignee=None,
                status=status,
                created_by=request.user,
            )
        except DomainError as exc:
            if is_htmx:
                status_code = 403 if "Status change requires" in str(exc) else 400
                return HttpResponse(str(exc), status=status_code)
            messages.error(request, str(exc))
            return redirect(
                "project-task-list",
                workspace_slug=self.project.workspace.slug,
                project_slug=self.project.slug,
            )

        if is_htmx:
            filter_search = request.POST.get("filter_search", "").strip() or None
            filter_priority = request.POST.get("filter_priority", "").strip() or None
            filter_assignee = request.POST.get("filter_assignee", "").strip() or None
            filter_tag = request.POST.get("filter_tag", "").strip() or None
            filter_is_overdue = request.POST.get("filter_is_overdue", "").strip() or None
            filter_is_archived = request.POST.get("filter_is_archived", "").strip()

            matches_filters = True
            if filter_search and filter_search.lower() not in task.title.lower():
                matches_filters = False
            if filter_priority and task.priority != filter_priority:
                matches_filters = False
            if filter_assignee:
                if filter_assignee == "unassigned" and task.assignee_id is not None:
                    matches_filters = False
                elif filter_assignee != "unassigned" and str(task.assignee_id) != filter_assignee:
                    matches_filters = False
            if filter_tag:
                matches_filters = False
            if filter_is_overdue == "true":
                matches_filters = False
            if filter_is_archived == "1":
                matches_filters = False

            if not matches_filters:
                response = HttpResponse("", status=200)
                response["HX-Trigger"] = json.dumps(
                    {"showMessage": "Task created (hidden by active filters)."}
                )
                return response

            column_count = get_project_tasks(project=self.project).filter(status=status).count()
            response = render(
                request,
                "tasks/partials/kanban_card.html",
                {
                    "task": task,
                    "project": self.project,
                    "can_change_task_status": (
                        is_workspace_admin or task.assignee_id == request.user.id
                    ),
                    "is_workspace_admin": is_workspace_admin,
                    "new_column_count": column_count,
                    "column_status": status,
                    "is_new_card": True,
                },
            )
            response["HX-Trigger"] = json.dumps({"showMessage": "Task created."})
            return response

        messages.success(request, "Task created.")
        return redirect(
            "project-task-list",
            workspace_slug=self.project.workspace.slug,
            project_slug=self.project.slug,
        )


class KanbanColumnLoadMoreView(ProjectTaskAccessMixin, View):
    def get(self, request, *args, **kwargs):
        status = request.GET.get("status", "").strip()
        if status not in TaskStatus.values:
            return HttpResponse("Invalid status.", status=400)

        cursor = request.GET.get("cursor", "").strip() or None

        try:
            offset = max(0, int(request.GET.get("offset", 0)))
        except (ValueError, TypeError):
            offset = 0

        try:
            limit = min(50, max(1, int(request.GET.get("limit", 20))))
        except (ValueError, TypeError):
            limit = 20

        search = request.GET.get("search", "").strip() or None
        priority = request.GET.get("priority", "").strip() or None
        assignee_id = request.GET.get("assignee", "").strip() or None
        tag_slug = request.GET.get("tag", "").strip() or None
        is_overdue = request.GET.get("is_overdue", "").strip() or None
        archived_param = request.GET.get("is_archived", "").strip()

        if archived_param in ("1", "true"):
            is_archived = True
        elif archived_param == "all":
            is_archived = None
        else:
            is_archived = False
            archived_param = "0"

        try:
            page_data = get_kanban_column_page(
                project=self.project,
                status=status,
                cursor=cursor,
                offset=offset,
                limit=limit,
                priority=priority,
                assignee_id=assignee_id,
                tag_slug=tag_slug,
                is_overdue=is_overdue,
                is_archived=is_archived,
                search=search,
            )
        except ValueError:
            page_data = get_kanban_column_page(
                project=self.project,
                status=status,
                cursor=cursor,
                offset=offset,
                limit=limit,
                is_archived=is_archived,
            )

        membership = get_workspace_membership(
            workspace=self.project.workspace,
            user=request.user,
        )
        is_workspace_admin = has_membership_role(membership, "owner", "admin")

        context = {
            "project": self.project,
            "status": status,
            "tasks": page_data["tasks"],
            "has_more": page_data["has_more"],
            "next_cursor": page_data["next_cursor"],
            "next_offset": page_data["next_offset"],
            "remaining_count": page_data["remaining_count"],
            "is_workspace_admin": is_workspace_admin,
            "can_change_task_status": is_workspace_admin,
            "current_filters": {
                "search": search or "",
                "status": status,
                "priority": priority or "",
                "assignee": assignee_id or "",
                "tag": tag_slug or "",
                "is_overdue": is_overdue or "",
                "is_archived": archived_param or "0",
            },
        }
        return render(request, "tasks/partials/kanban_column_slice.html", context)


class TaskUpdateView(TaskAccessMixin, FormView):
    allow_archived = False
    form_class = TaskUpdateForm
    template_name = "tasks/task_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["task"] = self.task
        kwargs["members"] = get_project_task_candidates(project=self.task.project)
        return kwargs

    def form_valid(self, form):
        try:
            if form.cleaned_data["assignee"] != self.task.assignee:
                if not can_assign_task(task=self.task, user=self.request.user):
                    raise PermissionDenied("Task assignment requires admin access.")

            if form.cleaned_data["status"] != self.task.status:
                if not can_change_task_status(task=self.task, user=self.request.user):
                    raise PermissionDenied("Status change requires admin access or assignee role.")
            self.task = update_task(
                task=self.task,
                actor=self.request.user,
                title=form.cleaned_data["title"],
                description=form.cleaned_data["description"],
                priority=form.cleaned_data["priority"],
                due_date=form.cleaned_data["due_date"],
                assignee=form.cleaned_data["assignee"],
                status=form.cleaned_data["status"],
            )
        except DomainError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)

        messages.success(self.request, "Task updated.")
        return redirect(
            "task-detail",
            workspace_slug=self.task.project.workspace.slug,
            project_slug=self.task.project.slug,
            task_slug=self.task.slug,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["task"] = self.task
        return context
