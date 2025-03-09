# forms.py
from django import forms
from .models import DocuSignTemplate


class NameEmailForm(forms.Form):
    name = forms.CharField(max_length=100, label="Name")
    email = forms.EmailField(label='Email')
    template_name = forms.ModelChoiceField(queryset=DocuSignTemplate.objects.all(), label='Template Name')

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)  # Get the logged-in user
        super(NameEmailForm, self).__init__(*args, **kwargs)

        # 🔹 Filter templates based on employer
        if user and user.employer:
            self.fields['template_name'].queryset = DocuSignTemplate.objects.filter(employer=user.employer)

        # Apply custom input styles
        for field_name, field in self.fields.items():
            if field_name != 'csrfmiddlewaretoken':  
                field.widget.attrs.update({'class': 'custom-input'})

        # Update the template_name widget to hide the text
        self.fields['template_name'].widget.attrs.update({
            'class': 'custom-input',
            'style': 'appearance: none; -webkit-appearance: none; -moz-appearance: none; text-indent: 1px; text-overflow: ""'
        })

    def clean(self):
        cleaned_data = super().clean()
        template_name = cleaned_data.get('template_name')

        if template_name:
            cleaned_data["template_id"] = template_name.template_id

        return cleaned_data