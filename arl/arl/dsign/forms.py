# forms.py
from django import forms
from .models import DocuSignTemplate


class NameEmailForm(forms.Form):
    name = forms.CharField(label='Name', max_length=100)
    email = forms.EmailField(label='Email')
    template_name = forms.CharField(label='Template Name', max_length=255)

    def clean_template_name(self):
        template_name = self.cleaned_data['template_name']
        try:
            template = DocuSignTemplate.objects.get(template_name=template_name)
            self.template_id = template.template_id
        except DocuSignTemplate.DoesNotExist:
            raise forms.ValidationError("Template name does not exist")
        return template_name

    def clean(self):
        cleaned_data = super().clean()
        if 'template_name' in cleaned_data:
            self.cleaned_data['template_id'] = getattr(self, 'template_id', None)
        return cleaned_data