from django import forms

from tasks.models import TaskPriority, TaskStatus


class TaskCreateForm(forms.Form):
    title = forms.CharField(max_length=255)
    description = forms.CharField(widget=forms.Textarea, required=False)
    priority = forms.ChoiceField(choices=TaskPriority.choices)
    due_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    assignee = forms.ChoiceField(required=False)

    def __init__(self, *args, members, **kwargs):
        super().__init__(*args, **kwargs)
        choices = [("", "---------")]
        choices.extend((str(member.id), member.username) for member in members)
        self.fields["assignee"].choices = choices
        self._members = {str(member.id): member for member in members}

    def clean_assignee(self):
        value = self.cleaned_data["assignee"]
        if not value:
            return None
        return self._members[value]


class TaskUpdateForm(forms.Form):
    status = forms.ChoiceField(choices=TaskStatus.choices)
    assignee = forms.ChoiceField(required=False)

    def __init__(self, *args, task, members, **kwargs):
        super().__init__(*args, **kwargs)
        choices = [("", "---------")]
        choices.extend((str(member.id), member.username) for member in members)
        self.fields["assignee"].choices = choices
        self._members = {str(member.id): member for member in members}
        self.fields["status"].initial = task.status
        self.fields["assignee"].initial = str(task.assignee_id) if task.assignee_id else ""

    def clean_assignee(self):
        value = self.cleaned_data["assignee"]
        if not value:
            return None
        return self._members[value]
