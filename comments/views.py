from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import redirect
from django.views.generic import FormView, View

from comments.forms import CommentForm
from comments.models import Comment
from comments.selectors import get_comment_by_id, get_task_comments
from comments.services import add_comment, soft_delete_comment
from core.exceptions import DomainError
from tasks.models import Task
from tasks.selectors import get_project_task_by_slug


class CommentTaskAccessMixin(LoginRequiredMixin):
    task = None

    def dispatch(self, request, *args, **kwargs):
        try:
            self.task = get_project_task_by_slug(
                workspace_slug=kwargs["workspace_slug"],
                project_slug=kwargs["project_slug"],
                task_slug=kwargs["task_slug"],
                user=request.user,
            )
        except Task.DoesNotExist as exc:
            raise Http404("Task not found.") from exc
        return super().dispatch(request, *args, **kwargs)


class CommentCreateView(CommentTaskAccessMixin, FormView):
    form_class = CommentForm

    def form_invalid(self, form):
        for errors in form.errors.values():
            for error in errors:
                messages.error(self.request, error)
        return redirect(
            "task-detail",
            workspace_slug=self.task.project.workspace.slug,
            project_slug=self.task.project.slug,
            task_slug=self.task.slug,
        )

    def form_valid(self, form):
        try:
            add_comment(
                task=self.task,
                author=self.request.user,
                text=form.cleaned_data["text"],
            )
        except DomainError as exc:
            messages.error(self.request, str(exc))
            return redirect(
                "task-detail",
                workspace_slug=self.task.project.workspace.slug,
                project_slug=self.task.project.slug,
                task_slug=self.task.slug,
            )

        messages.success(self.request, "Comment added.")
        return redirect(
            "task-detail",
            workspace_slug=self.task.project.workspace.slug,
            project_slug=self.task.project.slug,
            task_slug=self.task.slug,
        )


class CommentDeleteView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            comment = get_comment_by_id(comment_id=kwargs["comment_id"], user=request.user)
        except Comment.DoesNotExist as exc:
            raise Http404("Comment not found.") from exc

        try:
            soft_delete_comment(comment=comment, actor=request.user)
        except DomainError as exc:
            messages.error(request, str(exc))
            return redirect(
                "task-detail",
                workspace_slug=comment.task.project.workspace.slug,
                project_slug=comment.task.project.slug,
                task_slug=comment.task.slug,
            )

        messages.success(request, "Comment deleted.")
        return redirect(
            "task-detail",
            workspace_slug=comment.task.project.workspace.slug,
            project_slug=comment.task.project.slug,
            task_slug=comment.task.slug,
        )
