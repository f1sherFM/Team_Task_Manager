from django import forms


class ProjectCreateForm(forms.Form):
    name = forms.CharField(max_length=255)
    description = forms.CharField(widget=forms.Textarea, required=False)
