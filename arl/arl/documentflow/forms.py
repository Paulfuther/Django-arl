from django import forms
from arl.documentflow.models import DocumentFlow
from arl.user.models import Employer


STATUS_CHOICES = [
    ("", "No change"),
    ("sent", "Sent"),
    ("completed", "Completed"),
]


class OnboardingRepairFilterForm(forms.Form):
    employer = forms.ModelChoiceField(
        queryset=Employer.objects.none(),
        required=False,
        empty_label="Select employer",
        label="Employer",
    )
    flow = forms.ModelChoiceField(
        queryset=DocumentFlow.objects.none(),
        required=False,
        empty_label="Select active flow",
        label="Flow",
    )
    q = forms.CharField(
        required=False,
        label="Search",
        widget=forms.TextInput(attrs={"placeholder": "Search by name or email"}),
    )
    incomplete_only = forms.BooleanField(required=False, label="Incomplete only")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["employer"].queryset = Employer.objects.all().order_by("name")

        employer = None
        bound_data = self.data if self.is_bound else self.initial

        employer_id = bound_data.get("employer") if bound_data else None
        if employer_id:
            try:
                employer = Employer.objects.get(pk=employer_id)
            except Employer.DoesNotExist:
                employer = None

        if employer:
            self.fields["flow"].queryset = DocumentFlow.objects.filter(
                employer=employer,
                is_active=True,
            ).order_by("name")
        else:
            self.fields["flow"].queryset = DocumentFlow.objects.filter(
                is_active=True
            ).order_by("name")


class BulkDynamicRepairRowForm(forms.Form):
    apply = forms.BooleanField(required=False, label="Apply")
    user_id = forms.IntegerField(widget=forms.HiddenInput())

    def __init__(self, *args, steps=None, **kwargs):
        super().__init__(*args, **kwargs)
        steps = steps or []

        for step in steps:
            self.fields[f"step_{step.id}_employee_status"] = forms.ChoiceField(
                choices=STATUS_CHOICES,
                required=False,
                label=f"{step.template.template_name} employee",
            )
            self.fields[f"step_{step.id}_manager_status"] = forms.ChoiceField(
                choices=STATUS_CHOICES,
                required=False,
                label=f"{step.template.template_name} manager",
            )
            self.fields[f"step_{step.id}_manager_name"] = forms.CharField(
                required=False,
                max_length=255,
                label=f"{step.template.template_name} manager name",
            )
            self.fields[f"step_{step.id}_manager_email"] = forms.EmailField(
                required=False,
                label=f"{step.template.template_name} manager email",
            )