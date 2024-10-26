from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms
from django.contrib.auth.models import Group
from django.forms.widgets import ClearableFileInput
from arl.msg.models import EmailTemplate, WhatsAppTemplate


class SMSForm(forms.Form):
    message = forms.CharField(
        max_length=1000,
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": "Enter a message (max 1000 characters)",
                "class": "custom-input",
            }
        ),
        help_text="",
    )

    selected_group = forms.ModelChoiceField(
        queryset=Group.objects.all(),
        required=True,
        label="Select Group to Send SMS",
        widget=forms.Select(attrs={"class": "custom-input"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.add_input(Submit("submit", "Submit"))


class TemplateEmailForm(forms.Form):
    sendgrid_id = forms.ModelChoiceField(
        queryset=EmailTemplate.objects.all(), label="Select Template"
    )
    subject = forms.CharField(max_length=100, label="Subject")
    widget = forms.Textarea(
        attrs={
            "placeholder": "Enter a subject",
            "class": "custom-input",
        },
    )

    selected_group = forms.ModelChoiceField(
        queryset=Group.objects.all(),
        required=True,
        label="Select Group to Send Email",
        widget=forms.Select(attrs={"class": "custom-input"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name != 'csrfmiddlewaretoken':  # Skip CSRF token field
                field.widget.attrs.update({'class': 'custom-input'})


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

    def __init__(self, attrs=None):
        super().__init__(attrs)
        if attrs is None:
            attrs = {}
        attrs.update({'multiple': 'multiple'})
        self.attrs = attrs

    def value_from_datadict(self, data, files, name):
        return files.getlist(name)
    

class EmailForm(forms.Form):
    selected_group = forms.ModelChoiceField(
        queryset=Group.objects.all(),
        required=True,
        label="Select Group to Send Email",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    
    template_id = forms.ModelChoiceField(
        queryset=EmailTemplate.objects.all(),
        required=True,
        label="Select Email Template",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    attachment = forms.FileField(
        label="Attach File",
        widget=forms.ClearableFileInput(attrs={'class': 'form-control'}),
        required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name != 'csrfmiddlewaretoken':  # Skip CSRF token field
                field.widget.attrs.update({'class': 'form-control'})


class TemplateWhatsAppForm(forms.Form):
    whatsapp_id = forms.ModelChoiceField(
        queryset=WhatsAppTemplate.objects.all(), label="Select Template"
    )

    selected_group = forms.ModelChoiceField(
        queryset=Group.objects.all(),
        required=True,
        label="Select Group to Send Whatsapp",
        widget=forms.Select(attrs={"class": "custom-input"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name != 'csrfmiddlewaretoken':  # Skip CSRF token field
                field.widget.attrs.update({'class': 'custom-input'})


class SendGridFilterForm(forms.Form):
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="From"
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="To"
    )
    template_id = forms.ModelChoiceField(
        queryset=EmailTemplate.objects.all(),
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Template Name"
    )