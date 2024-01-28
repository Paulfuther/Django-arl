# forms.py
from django import forms
from .models import DocuSignTemplate


class NameEmailForm(forms.Form):
    name = forms.CharField(max_length=100, label="Subject")
    email = forms.EmailField(label='Email')
    template_name = forms.ModelChoiceField(queryset=DocuSignTemplate.objects.all(), label='Template Name')

    def __init__(self, *args, **kwargs):
        super(NameEmailForm, self).__init__(*args, **kwargs)

        for field_name, field in self.fields.items():
            if field_name != 'csrfmiddlewaretoken':  # Skip CSRF token field
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
            try:
                template = DocuSignTemplate.objects.get(template_name=template_name)
                cleaned_data['template_id'] = template.template_id
            except DocuSignTemplate.DoesNotExist:
                raise forms.ValidationError("Selected template does not exist")

        return cleaned_data