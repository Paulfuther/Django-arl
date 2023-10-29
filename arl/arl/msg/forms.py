from django import forms


class SMSForm(forms.Form):
    phone_number = forms.CharField(max_length=15, help_text="Enter a valid phone number")

    message = forms.CharField(
        max_length=100,
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text="Enter a message (max 100 characters)",
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