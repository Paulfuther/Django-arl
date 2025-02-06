from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.urls import reverse_lazy

from .models import CustomUser, Store


class CustomUserCreationForm(UserCreationForm):
    store = forms.ModelChoiceField(
        queryset=Store.objects.all(),
        empty_label="Select a store",
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = (
            "employer",
            "store",
            "username",
            "password1",
            "password2",
            "first_name",
            "last_name",
            "dob",
            "email",
            "sin",
            "address",
            "address_two",
            "city",
            "state_province",
            "country",
            "postal",
        )
        widgets = {
            'dob': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self.fields["address"].required = True
        self.fields["address_two"].required = False
        self.fields["city"].required = True
        self.fields["state_province"].required = True
        self.fields["country"].required = True
        self.fields["postal"].required = True
        self.fields["email"].required = True
        self.fields["sin"].required = True
        self.fields['dob'].required = True
        self.fields['postal'].required = True
        # Populate choices for manager_dropdown
        # managers = CustomUser.objects.filter(groups__name='Manager')
        # manager_choices = [(manager.id, manager.username) for manager in managers]
        # self.fields['manager_dropdown'].choices = [('', 'Select a manager')] + manager_choices
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.add_input(Submit("submit", "Register"))
        self.helper.form_action = reverse_lazy("index")
        # Optionally set an empty label for the dropdown
        self.fields["store"].empty_label = "Select a Store"
        self.fields["store"].required = True
        # Apply margin-top or margin-bottom to all fields
        for field_name in self.fields:
            self.fields[field_name].widget.attrs["class"] = "mt-1"  # Apply margin-top
            self.fields[field_name].widget.attrs["class"] = "mb-2"  # Apply margin-bottom

    def clean_email(self):
        email = self.cleaned_data['email']
        return email.lower()  # Convert email to lowercase

    def clean(self):
        cleaned_data = super().clean()
        phone_number = cleaned_data.get("phone_number")
        email = cleaned_data.get("email")
        if phone_number and CustomUser.objects.filter(phone_number=phone_number).exists():
            self.add_error("phone_number", "This phone number is already in use.")
        if email and CustomUser.objects.filter(email=email).exists():
            self.add_error("email", "This email is already in use")

        return cleaned_data


class TwoFactorAuthenticationForm(forms.Form):
    verification_code = forms.CharField(
        max_length=12,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )

    def __init__(self, *args, **kwargs):
        super(TwoFactorAuthenticationForm, self).__init__(*args, **kwargs)
        self.fields['verification_code'].widget.attrs.update({'style': 'margin: 10px 0;'})