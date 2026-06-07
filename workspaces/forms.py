from django import forms

from workspaces.models import MembershipRole


class WorkspaceCreateForm(forms.Form):
    name = forms.CharField(max_length=255)


class InvitationCreateForm(forms.Form):
    email = forms.EmailField()
    role = forms.ChoiceField(
        choices=(
            (MembershipRole.ADMIN, "Admin"),
            (MembershipRole.MEMBER, "Member"),
        )
    )
