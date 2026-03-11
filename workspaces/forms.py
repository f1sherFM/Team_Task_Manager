from django import forms


class WorkspaceCreateForm(forms.Form):
    name = forms.CharField(max_length=255)
