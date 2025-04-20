# forms.py
from django import forms
from .models import DocuSignTemplate
from arl.user.models import CustomUser, Employer
from django.db.models.functions import Concat
from django.db.models import Value, F
from django.db.models import CharField
from django.forms.widgets import RadioSelect


class NameEmailForm(forms.Form):
    recipient = forms.ModelChoiceField(
        queryset=CustomUser.objects.none(),
        label="Select Employee",
        widget=RadioSelect,
        required=True
    )
    template_name = forms.ModelChoiceField(
        queryset=DocuSignTemplate.objects.none(),
        label='Template Name',
        widget=RadioSelect,
        required=True
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user and user.employer:
            self.fields['template_name'].queryset = DocuSignTemplate.objects.filter(
                employer=user.employer,
                is_ready_to_send=True  # ✅ Filter ready ones
            )
            self.fields['recipient'].queryset = CustomUser.objects.filter(
                employer=user.employer,
                is_active=True
            )

        self.fields['recipient'].label_from_instance = lambda obj: f"{obj.get_full_name()} ({obj.email})"

    def clean(self):
        cleaned_data = super().clean()
        template_name = cleaned_data.get('template_name')
        if template_name:
            cleaned_data["template_id"] = template_name.template_id
        return cleaned_data


class MultiSignedDocUploadForm(forms.Form):
    user = forms.ModelChoiceField(
        queryset=CustomUser.objects.filter(is_active=True)
                .annotate(
                full_name_email=Concat(
                    F('first_name'), Value(' '),
                    F('last_name'), Value(' <'),
                    F('email'), Value('>'),
                    output_field=CharField()
                )
            ).order_by('first_name', 'last_name'),
        label="Select User",
        to_field_name='id',
    )

    employer = forms.ModelChoiceField(
        queryset=Employer.objects.all().order_by('name'),
        label="Select Employer"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['user'].label_from_instance = lambda obj: obj.full_name_email