from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
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
        return super().dispatch(request, *args, **kwargs)


class CommentCreateView(CommentTaskAccessMixin, FormView):
    form_class = CommentForm

    def form_invalid(self, form):
        if self.request.headers.get("HX-Request") == "true":
            return render(
                self.request,
                "comments/partials/comment_form.html",
                {
                    "task": self.task,
                    "comment_form": form,
                },
                status=200,
            )
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
            comment = add_comment(
                task=self.task,
                author=self.request.user,
                text=form.cleaned_data["text"],
            )
        except DomainError as exc:
            if self.request.headers.get("HX-Request") == "true":
                form.add_error(None, str(exc))
                return render(
                    self.request,
                    "comments/partials/comment_form.html",
                    {
                        "task": self.task,
                        "comment_form": form,
                    },
                    status=200,
                )
            messages.error(self.request, str(exc))
            return redirect(
                "task-detail",
                workspace_slug=self.task.project.workspace.slug,
                project_slug=self.task.project.slug,
                task_slug=self.task.slug,
            )

        if self.request.headers.get("HX-Request") == "true":
            comments_count = get_task_comments(task=self.task).count()
            return render(
                self.request,
                "comments/partials/comment_create_response.html",
                {
                    "task": self.task,
                    "comment": comment,
                    "comment_form": CommentForm(),
                    "comments_count": comments_count,
                },
                status=200,
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

        is_htmx = request.headers.get("HX-Request") == "true"

        try:
            comment = soft_delete_comment(comment=comment, actor=request.user)
        except DomainError as exc:
            if is_htmx:
                return HttpResponse(str(exc), status=403)
            messages.error(request, str(exc))
            return redirect(
                "task-detail",
                workspace_slug=comment.task.project.workspace.slug,
                project_slug=comment.task.project.slug,
                task_slug=comment.task.slug,
            )

        if is_htmx:
            return render(
                request,
                "comments/partials/comment_item.html",
                {
                    "comment": comment,
                    "can_delete_comment": False,
                },
            )

        messages.success(request, "Comment deleted.")
        return redirect(
            "task-detail",
            workspace_slug=comment.task.project.workspace.slug,
            project_slug=comment.task.project.slug,
            task_slug=comment.task.slug,
        )
