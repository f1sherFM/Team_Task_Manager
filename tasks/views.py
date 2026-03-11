from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import redirect
from django.views.generic import FormView, TemplateView

from comments.forms import CommentForm
from comments.selectors import get_task_comments
from core.exceptions import DomainError
from core.permissions import (
    can_assign_task,
    can_change_task_status,
    can_create_task,
    can_delete_comment,
)
from tasks.forms import TaskCreateForm, TaskUpdateForm
from tasks.models import Task
from tasks.selectors import (
    get_project_task_candidates,
    get_project_tasks,
    get_task_by_slug,
)
from tasks.services import assign_task, change_task_status, create_task
from projects.models import Project
from projects.selectors import get_project_by_slug


class ProjectTaskAccessMixin(LoginRequiredMixin):
    project = None

    def dispatch(self, request, *args, **kwargs):
        try:
            self.project = get_project_by_slug(slug=kwargs["project_slug"], user=request.user)
        except Project.DoesNotExist as exc:
            raise Http404("Project not found.") from exc
        return super().dispatch(request, *args, **kwargs)


class TaskAccessMixin(LoginRequiredMixin):
    task = None

    def dispatch(self, request, *args, **kwargs):
        try:
            self.task = get_task_by_slug(slug=kwargs["slug"], user=request.user)
        except Task.DoesNotExist as exc:
            raise Http404("Task not found.") from exc
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
        context["project"] = self.project
        context["tasks"] = get_project_tasks(project=self.project)
        context["can_create_task"] = can_create_task(project=self.project, user=self.request.user)
        return context

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
        return redirect("task-detail", slug=task.slug)


class TaskDetailView(TaskAccessMixin, TemplateView):
    template_name = "tasks/task_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        comments = list(get_task_comments(task=self.task))
        context["task"] = self.task
        context["comments"] = comments
        context["comment_form"] = CommentForm()
        context["deletable_comment_ids"] = {
            comment.id
            for comment in comments
            if can_delete_comment(comment=comment, user=self.request.user)
        }
        return context


class TaskUpdateView(TaskAccessMixin, FormView):
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
                self.task = assign_task(
                    task=self.task,
                    assignee=form.cleaned_data["assignee"],
                    actor=self.request.user,
                )

            if form.cleaned_data["status"] != self.task.status:
                if not can_change_task_status(task=self.task, user=self.request.user):
                    raise PermissionDenied("Status change requires admin access or assignee role.")
                self.task = change_task_status(
                    task=self.task,
                    status=form.cleaned_data["status"],
                    actor=self.request.user,
                )
        except DomainError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)

        messages.success(self.request, "Task updated.")
        return redirect("task-detail", slug=self.task.slug)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["task"] = self.task
        return context
