from django import forms
from arl.user.models import CustomUser
from django.contrib.auth.models import Group 
from arl.msg.models import EmailTemplate

class SMSForm(forms.Form):
    message = forms.CharField(
        max_length=100,
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text="Enter a message (max 200 characters)",
    )

    selected_group = forms.ModelChoiceField(
        queryset=Group.objects.all(),
        empty_label="Select a group",
        required=False,
        label="Select Group to Send SMS"
    )

class TemplateEmailForm(forms.Form):
    sendgrid_id = forms.ModelChoiceField(queryset=EmailTemplate.objects.all(), label='Select Template')
    subject = forms.CharField(max_length=100, label='Subject')

    selected_group = forms.ModelChoiceField(
        queryset=Group.objects.all(),
        empty_label="Select a group",
        required=False,
        label="Select Group to Send Email"
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
  