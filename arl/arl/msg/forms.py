from django import forms


class SMSForm(forms.Form):
    phone_number = forms.CharField(max_length=15, help_text="Enter a valid phone number")
