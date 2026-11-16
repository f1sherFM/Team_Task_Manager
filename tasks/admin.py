from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from core.exceptions import DomainError
from tasks.models import Task, TaskChecklistItem, TaskTag
from tasks.services import (
    UNSET,
    add_checklist_item,
    archive_task,
    create_task,
    create_task_tag,
    delete_checklist_item,
    delete_task,
    delete_task_tag,
    restore_task,
    set_task_tags,
    update_checklist_item,
    update_task,
    update_task_tag,
)


class TaskAdminForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        project = cleaned_data.get("project") or (
            self.instance.project if self.instance.pk else None
        )
        tags = cleaned_data.get("tags")
        if project and tags:
            workspace = project.workspace
            invalid_tags = [tag.name for tag in tags if tag.workspace_id != workspace.id]
            if invalid_tags:
                raise ValidationError(
                    {
                        "tags": (
                            f"Tags do not belong to the task workspace: {', '.join(invalid_tags)}"
                        )
                    }
                )

        if self.instance.pk and self.instance.is_archived and self.has_changed():
            raise ValidationError(
                "Archived tasks cannot be edited. Restore the task first to make changes."
            )
        return cleaned_data


class TaskChecklistItemInline(admin.TabularInline):
    model = TaskChecklistItem
    extra = 1
    readonly_fields = ("position",)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    form = TaskAdminForm
    list_display = (
        "title",
        "project",
        "status",
        "priority",
        "assignee",
        "due_date",
        "is_archived",
    )
    list_filter = ("status", "priority", "is_archived", "project")
    search_fields = ("title", "slug", "project__name", "created_by__username")
    filter_horizontal = ("tags",)
    readonly_fields = ("slug", "is_archived", "created_by")
    actions = ("archive_selected_tasks", "restore_selected_tasks")
    inlines = [TaskChecklistItemInline]

    @admin.action(description="Archive selected tasks")
    def archive_selected_tasks(self, request, queryset):
        success_count = 0
        for task in queryset:
            try:
                archive_task(task=task, actor=request.user)
                success_count += 1
            except DomainError as exc:
                self.message_user(
                    request,
                    f"Failed to archive task '{task.title}': {exc}",
                    level=messages.ERROR,
                )
        if success_count:
            self.message_user(
                request,
                f"Successfully archived {success_count} task(s).",
                level=messages.SUCCESS,
            )

    @admin.action(description="Restore selected tasks")
    def restore_selected_tasks(self, request, queryset):
        success_count = 0
        for task in queryset:
            try:
                restore_task(task=task, actor=request.user)
                success_count += 1
            except DomainError as exc:
                self.message_user(
                    request,
                    f"Failed to restore task '{task.title}': {exc}",
                    level=messages.ERROR,
                )
        if success_count:
            self.message_user(
                request,
                f"Successfully restored {success_count} task(s).",
                level=messages.SUCCESS,
            )

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "tags":
            object_id = (
                request.resolver_match.kwargs.get("object_id")
                if request.resolver_match
                else None
            )
            if object_id:
                try:
                    task = Task.objects.select_related("project__workspace").get(pk=object_id)
                    kwargs["queryset"] = TaskTag.objects.filter(workspace=task.project.workspace)
                except (Task.DoesNotExist, ValueError):
                    kwargs["queryset"] = TaskTag.objects.none()
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not change:
            task = create_task(
                project=obj.project,
                created_by=request.user,
                title=obj.title,
                description=obj.description,
                priority=obj.priority,
                due_date=obj.due_date,
                assignee=obj.assignee,
            )
            obj.id = task.id
            obj.slug = task.slug
        else:
            db_task = Task.objects.select_related("project__workspace").get(pk=obj.pk)
            if db_task.is_archived:
                raise ValidationError("Archived tasks cannot be edited. Restore the task first.")
            update_task(
                task=db_task,
                actor=request.user,
                title=form.cleaned_data.get("title", UNSET),
                description=form.cleaned_data.get("description", UNSET),
                priority=form.cleaned_data.get("priority", UNSET),
                due_date=form.cleaned_data.get("due_date", UNSET),
                assignee=form.cleaned_data.get("assignee", UNSET),
                status=form.cleaned_data.get("status", UNSET),
            )

    def save_related(self, request, form, formsets, change):
        # Save inlines first without triggering form.save_m2m()
        for formset in formsets:
            self.save_formset(request, form, formset, change=change)

        # Handle tags explicitly through domain service without double saving
        if not change or "tags" in form.changed_data:
            tags = form.cleaned_data.get("tags")
            if tags is not None:
                workspace = form.instance.project.workspace
                for tag in tags:
                    if tag.workspace_id != workspace.id:
                        raise ValidationError(
                            f"Tag '{tag.name}' does not belong to workspace '{workspace.name}'."
                        )
                set_task_tags(task=form.instance, tags=list(tags), actor=request.user)

    def save_formset(self, request, form, formset, change):
        if formset.model == TaskChecklistItem:
            formset.save(commit=False)
            for obj in formset.deleted_objects:
                delete_checklist_item(item=obj, actor=request.user)
            for inline_form in formset.forms:
                if inline_form.is_valid() and inline_form.has_changed():
                    instance = inline_form.instance
                    if instance in formset.deleted_objects:
                        continue
                    if instance.pk is None:
                        if inline_form.cleaned_data.get("text"):
                            add_checklist_item(
                                task=form.instance,
                                text=inline_form.cleaned_data["text"],
                                actor=request.user,
                                is_completed=inline_form.cleaned_data.get("is_completed", False),
                            )
                    else:
                        db_item = TaskChecklistItem.objects.get(pk=instance.pk)
                        update_checklist_item(
                            item=db_item,
                            actor=request.user,
                            text=inline_form.cleaned_data.get("text", UNSET),
                            is_completed=inline_form.cleaned_data.get("is_completed", UNSET),
                        )
        else:
            super().save_formset(request, form, formset, change)

    def delete_model(self, request, obj):
        delete_task(task=obj, actor=request.user)

    def delete_queryset(self, request, queryset):
        for task in queryset:
            delete_task(task=task, actor=request.user)


class TaskTagAdminForm(forms.ModelForm):
    class Meta:
        model = TaskTag
        fields = ("workspace", "name", "color")

    def clean_workspace(self):
        workspace = self.cleaned_data.get("workspace")
        if self.instance.pk and self.instance.workspace_id != workspace.id:
            raise ValidationError("Moving a tag to a different workspace is not allowed.")
        return workspace


@admin.register(TaskTag)
class TaskTagAdmin(admin.ModelAdmin):
    form = TaskTagAdminForm
    list_display = ("name", "slug", "workspace", "color", "created_at")
    list_filter = ("workspace",)
    search_fields = ("name", "slug", "workspace__name")

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ("slug", "workspace", "created_at")
        return ("slug", "created_at")

    def save_model(self, request, obj, form, change):
        if not change:
            tag = create_task_tag(
                workspace=obj.workspace,
                name=obj.name,
                color=obj.color,
                actor=request.user,
            )
            obj.id = tag.id
            obj.slug = tag.slug
        else:
            db_tag = TaskTag.objects.get(pk=obj.pk)
            update_task_tag(
                tag=db_tag,
                actor=request.user,
                name=form.cleaned_data.get("name", UNSET),
                color=form.cleaned_data.get("color", UNSET),
            )

    def delete_model(self, request, obj):
        delete_task_tag(tag=obj, actor=request.user)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            delete_task_tag(tag=obj, actor=request.user)


class TaskChecklistItemAdminForm(forms.ModelForm):
    class Meta:
        model = TaskChecklistItem
        fields = ("task", "text", "is_completed")

    def clean_task(self):
        task = self.cleaned_data.get("task")
        if self.instance.pk and self.instance.task_id != task.id:
            raise ValidationError("Moving a checklist item to a different task is not allowed.")
        return task


@admin.register(TaskChecklistItem)
class TaskChecklistItemAdmin(admin.ModelAdmin):
    form = TaskChecklistItemAdminForm
    list_display = ("text", "task", "position", "is_completed", "created_at")
    list_filter = ("is_completed",)
    search_fields = ("text", "task__title")

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ("task", "position", "created_at")
        return ("position", "created_at")

    def save_model(self, request, obj, form, change):
        if not change:
            item = add_checklist_item(
                task=obj.task,
                text=obj.text,
                actor=request.user,
                is_completed=obj.is_completed,
            )
            obj.id = item.id
            obj.position = item.position
        else:
            db_item = TaskChecklistItem.objects.get(pk=obj.pk)
            update_checklist_item(
                item=db_item,
                actor=request.user,
                text=form.cleaned_data.get("text", UNSET),
                is_completed=form.cleaned_data.get("is_completed", UNSET),
            )

    def delete_model(self, request, obj):
        delete_checklist_item(item=obj, actor=request.user)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            delete_checklist_item(item=obj, actor=request.user)
