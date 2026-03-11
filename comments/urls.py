from django.urls import path

from comments.views import CommentCreateView, CommentDeleteView


urlpatterns = [
    path("tasks/<slug:slug>/comments/add/", CommentCreateView.as_view(), name="comment-create"),
    path("comments/<int:comment_id>/delete/", CommentDeleteView.as_view(), name="comment-delete"),
]
