from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.urls import reverse_lazy
from .models import CustomUser, Store, Employer, NewHireInvite, EmployerRequest
from phonenumber_field.formfields import PhoneNumberField
from django.utils.crypto import get_random_string


class CustomUserCreationForm(UserCreationForm):
    store = forms.ModelChoiceField(
        queryset=Store.objects.all(),
        empty_label="Select a store",
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    employer = forms.ModelChoiceField(
        queryset=Employer.objects.all(),
        required=False,
        widget=forms.Select(attrs={"class": "form-control", "readonly": "readonly"}),  # Prepopulate & disable selection
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
            "sin_expiration_date",
            "work_permit_expiration_date",
            "address",
            "address_two",
            "city",
            "state_province",
            "country",
            "postal",
        )
        widgets = {
            'dob': forms.DateInput(attrs={'type': 'date'}),
            'sin_expiration_date': forms.DateInput(attrs={'type': 'date'}),
            'work_permit_expiration_date': forms.DateInput(attrs={'type': 'date'}),
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
        # self.fields['phone_number'].required = True
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
        sin = cleaned_data.get("sin")
        sin_expiration_date = cleaned_data.get("sin_expiration_date")
        work_permit_expiration_date = cleaned_data.get("work_permit_expiration_date")

        if sin and sin.startswith('9'):
            if not sin_expiration_date:
                self.add_error("sin_expiration_date", "SIN expiration date is required for SINs starting with 9.")
            if not work_permit_expiration_date:
                self.add_error("work_permit_expiration_date", "Work permit expiration date is required for SINs starting with 9.")

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


class EmployerRegistrationForm(forms.ModelForm):
    """Form for new employers to request access."""

    senior_contact_name = forms.CharField(
        max_length=255,
        required=True,
        label="Senior Contact Name",
        help_text="Who is responsible for employee onboarding?"
    )
    phone_number = PhoneNumberField(
        required=True,
        label="Contact Phone Number"
    )
    verified_sender_local = forms.CharField(
        max_length=50,
        required=True,
        label="Verified Email (Local Part)",
        help_text="Enter only the part before '@1553690ontarioinc.com'"
    )

    class Meta:
        model = EmployerRequest
        fields = [
            "name",
            "email",
            "address",
            "address_two",
            "city",
            "state_province",
            "country",
            "phone_number",
            "senior_contact_name",
            "verified_sender_local",  # ✅ Updated field
        ]
    
    def clean_verified_sender_local(self):
        """Ensure only the local part is stored and is unique."""
        email_local_part = self.cleaned_data.get("verified_sender_local")

        # Ensure no '@' symbol is included
        if "@" in email_local_part:
            raise forms.ValidationError("Only enter the part before '@yourdomain.com'.")

        # Check if this email (with domain) already exists
        full_email = f"{email_local_part}@1553690ontarioinc.com"
        if Employer.objects.filter(verified_sender_local=email_local_part).exists():
            raise forms.ValidationError("An employer with this email already exists.")

        return email_local_part


class NewHireInviteForm(forms.ModelForm):
    class Meta:
        model = NewHireInvite
        fields = ["email", "name", "role"]  # Store removed
        widgets = {
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "Enter new hire's email"}),
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Full Name"}),
            "role": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        self.employer = kwargs.pop("employer", None)
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        invite = super().save(commit=False)
        invite.employer = self.employer  # Assign the employer automatically
        invite.token = invite.token or get_random_string(64)
        if commit:
            invite.save()
        return invite