from django import forms
from arl.user.models import CustomUser


class SMSForm(forms.Form):
    message = forms.CharField(
        max_length=100,
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text="Enter a message (max 200 characters)",
    )

    selected_users = forms.ModelMultipleChoiceField(
        queryset=CustomUser.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Select Users to Send SMS"
    )

class TemplateEmailForm(forms.Form):
    to_email = forms.EmailField(
        label='To Email',
        widget=forms.EmailInput(attrs={'class': 'form-control'}),
        help_text='Enter a valid email address'
    )
    subject = forms.CharField(
        label='Subject',
        max_length=255,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text='Enter the email subject'
    )
    name = forms.CharField(
        label='Name',
        max_length=255,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text='Enter the recipient\'s name'
    )
    template_id = forms.CharField(
        label='Template ID',
        max_length=255,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text='Enter the email template ID'
    )

class EmailForm(forms.Form):
    to_email = forms.EmailField(
        label='To Email',
        widget=forms.EmailInput(attrs={'class': 'form-control'}),
        help_text='Enter a valid email address'
    )
    subject = forms.CharField(
        label='Subject',
        max_length=255,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text='Enter the email subject'
    )
    body = forms.CharField(
        label='Body',
        max_length=255,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text='Enter Body of Email'
    )
  