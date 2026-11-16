from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse
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
from tasks.models import Task, TaskStatus
from tasks.selectors import (
    filter_tasks,
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
        search = self.request.GET.get("search", "").strip() or None
        status_val = self.request.GET.get("status", "").strip() or None
        priority = self.request.GET.get("priority", "").strip() or None
        assignee_id = self.request.GET.get("assignee", "").strip() or None
        tag_slug = self.request.GET.get("tag", "").strip() or None
        is_overdue = self.request.GET.get("is_overdue", "").strip() or None
        archived_param = self.request.GET.get("is_archived", "").strip()

        if archived_param == "1":
            is_archived = True
        elif archived_param == "all":
            is_archived = None
        else:
            is_archived = False

        tasks_qs = get_project_tasks(project=self.project)
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

        paginator = Paginator(tasks_qs, 20)
        page_obj = paginator.get_page(self.request.GET.get("page"))

        membership = get_workspace_membership(
            workspace=self.project.workspace,
            user=self.request.user,
        )
        is_workspace_admin = has_membership_role(membership, "owner", "admin")

        context["project"] = self.project
        context["tasks"] = page_obj
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
        context["htmx_target"] = "#task-list-container"
        return context

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get("HX-Request") == "true":
            return self.response_class(
                request=self.request,
                template="tasks/partials/task_list_container.html",
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
        new_status = request.POST.get("status")

        if not new_status or new_status not in TaskStatus.values:
            if is_htmx:
                return HttpResponse("Invalid task status.", status=400)
            messages.error(request, "Invalid task status.")
            return redirect(
                "task-detail",
                workspace_slug=self.task.project.workspace.slug,
                project_slug=self.task.project.slug,
                task_slug=self.task.slug,
            )

        if not can_change_task_status(task=self.task, user=request.user):
            if is_htmx:
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
            if is_htmx:
                return HttpResponse(str(exc), status=400)
            messages.error(request, str(exc))
            return redirect(
                "task-detail",
                workspace_slug=self.task.project.workspace.slug,
                project_slug=self.task.project.slug,
                task_slug=self.task.slug,
            )

        if is_htmx:
            membership = get_workspace_membership(
                workspace=self.task.project.workspace,
                user=request.user,
            )
            is_workspace_admin = has_membership_role(membership, "owner", "admin")
            return render(
                request,
                "tasks/partials/task_status_dropdown.html",
                {
                    "task": self.task,
                    "can_change_status": True,
                    "is_workspace_admin": is_workspace_admin,
                },
            )

        messages.success(request, f"Task status updated to {self.task.get_status_display()}.")
        return redirect(
            "task-detail",
            workspace_slug=self.task.project.workspace.slug,
            project_slug=self.task.project.slug,
            task_slug=self.task.slug,
        )


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
