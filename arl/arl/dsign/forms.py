# forms.py
from django import forms
from .models import DocuSignTemplate


class NameEmailForm(forms.Form):
    name = forms.CharField(label='Name', max_length=100)
    email = forms.EmailField(label='Email')
    template_name = forms.ChoiceField(label='Template Name', choices=[])

    def __init__(self, *args, **kwargs):
        super(NameEmailForm, self).__init__(*args, **kwargs)
        self.fields['template_name'].choices = self.get_template_choices()

    def get_template_choices(self):
        choices = [('', 'Select a template')]  # Initial default choice
        templates = DocuSignTemplate.objects.all()  # Fetch all DocuSign templates
        for template in templates:
            choices.append((template.template_name, template.template_name))
        return choices

    def clean(self):
        cleaned_data = super().clean()
        template_name = cleaned_data.get('template_name')

        if template_name:
            try:
                template = DocuSignTemplate.objects.get(template_name=template_name)
                cleaned_data['template_id'] = template.template_id
            except DocuSignTemplate.DoesNotExist:
                raise forms.ValidationError("Selected template does not exist")

        return cleaned_data