# forms.py
from django import forms
from .models import DocuSignTemplate
from arl.user.models import CustomUser


class NameEmailForm(forms.Form):
    recipient = forms.ModelChoiceField(
        queryset=CustomUser.objects.none(),
        label="Select Employee"
    )
    template_name = forms.ModelChoiceField(queryset=DocuSignTemplate.objects.all(), label='Template Name')

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super(NameEmailForm, self).__init__(*args, **kwargs)

        if user and user.employer:
            # Limit templates by employer
            self.fields['template_name'].queryset = DocuSignTemplate.objects.filter(employer=user.employer)
            # Limit recipients to active users under the same employer
            self.fields['recipient'].queryset = CustomUser.objects.filter(employer=user.employer, is_active=True)

        # Add custom styling to fields
        for field_name, field in self.fields.items():
            field.widget.attrs.update({'class': 'custom-input'})

        # Special style for dropdown
        self.fields['template_name'].widget.attrs.update({
            'style': 'appearance: none; -webkit-appearance: none; -moz-appearance: none; text-indent: 1px; text-overflow: ""'
        })
        self.fields['recipient'].label_from_instance = lambda obj: f"{obj.get_full_name()} ({obj.email})"

    def clean(self):
        cleaned_data = super().clean()
        template_name = cleaned_data.get('template_name')
        if template_name:
            cleaned_data["template_id"] = template_name.template_id
        return cleaned_data