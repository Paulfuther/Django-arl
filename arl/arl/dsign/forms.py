# forms.py
from django import forms
from django.db.models import CharField, F, Value
from django.db.models.functions import Concat
from django.forms.widgets import RadioSelect

from arl.user.models import CustomUser, Employer

from .models import DocuSignTemplate


class NameEmailForm(forms.Form):
    recipient = forms.ModelChoiceField(
        queryset=CustomUser.objects.none(),
        label="Select Employee",
        widget=RadioSelect,
        required=True,
    )
    template_name = forms.ModelChoiceField(
        queryset=DocuSignTemplate.objects.none(),
        label="Template Name",
        widget=RadioSelect,
        required=True,
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        if user and user.employer:
            self.fields["template_name"].queryset = DocuSignTemplate.objects.filter(
                employer=user.employer,
                is_ready_to_send=True,  # ✅ Filter ready ones
            )
            self.fields["recipient"].queryset = CustomUser.objects.filter(
                employer=user.employer, is_active=True
            )

        self.fields["recipient"].label_from_instance = (
            lambda obj: f"{obj.get_full_name()} ({obj.email})"
        )

    def clean(self):
        cleaned_data = super().clean()
        template_name = cleaned_data.get("template_name")
        if template_name:
            cleaned_data["template_id"] = template_name.template_id
        return cleaned_data


class MultiSignedDocUploadForm(forms.Form):
    user = forms.ModelChoiceField(
        queryset=CustomUser.objects.filter(is_active=True)
        .annotate(
            full_name_email=Concat(
                F("first_name"),
                Value(" "),
                F("last_name"),
                Value(" <"),
                F("email"),
                Value(">"),
                output_field=CharField(),
            )
        )
        .order_by("first_name", "last_name"),
        label="Select User",
        to_field_name="id",
    )

    employer = forms.ModelChoiceField(
        queryset=Employer.objects.all().order_by("name"), label="Select Employer"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["user"].label_from_instance = lambda obj: obj.full_name_email


class EmployeeDocUploadForm(forms.Form):
    user = forms.ModelChoiceField(
        queryset=CustomUser.objects.none(),  # set in __init__
        label="Employee",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    document_title = forms.CharField(
        required=False,
        label="Title (optional)",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "e.g., SIN, Work Permit, ID"}
        ),
    )
    notes = forms.CharField(
        required=False,
        label="Notes (optional)",
        widget=forms.Textarea(
            attrs={"rows": 2, "class": "form-control", "placeholder": "Any notes…"}
        ),
    )
    iles = forms.FileField(
        label="Files",
        widget=forms.FileInput(
            attrs={
                "class": "form-control",
                "accept": ".pdf,.doc,.docx,.xls,.xlsx,.png,.jpg,.jpeg,.heic,.heif,.txt,.csv,.rtf,.webp,image/*,application/pdf",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        employer = kwargs.pop("employer", None)
        super().__init__(*args, **kwargs)
        qs = CustomUser.objects.filter(is_active=True)
        if employer:
            qs = qs.filter(employer=employer)
        self.fields["user"].queryset = qs.order_by("first_name", "last_name")
