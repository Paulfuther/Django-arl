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
        queryset=Store.objects.none(),
        required=False,  # ✅ Make store optional for employers
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    employer = forms.ModelChoiceField(
        queryset=Employer.objects.all(),
        required=False,
        widget=forms.Select(attrs={"class": "form-control", "readonly": "readonly"}),
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
            "phone_number",
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
        employer = kwargs.pop("employer", None)
        user_role = kwargs.pop("role", None)  # ✅ Get role from view or invite
        super().__init__(*args, **kwargs)

        # ✅ Set employer field
        if employer:
            self.fields["employer"].initial = employer
            stores = Store.objects.filter(employer=employer)

            if user_role == "EMPLOYER":
                # ✅ Employers do not need a store
                self.fields["store"].queryset = Store.objects.none()
                self.fields["store"].widget.attrs["disabled"] = "disabled"  # Prevent selection
                self.fields["store"].empty_label = "No store (You can add one later)"
                self.fields["store"].required = False
            else:
                # ✅ Managers and GSAs should see employer's stores
                self.fields["store"].queryset = stores
                if not stores.exists():
                    self.fields["store"].empty_label = "No store yet (Check with admin)"
                self.fields["store"].required = True
        else:
            # If no employer is provided, the store list is empty
            self.fields["store"].queryset = Store.objects.none()

        # ✅ Ensure phone number retains input after a failed form submission
        phone_number_value = self.data.get("phone_number") or (self.instance.phone_number if self.instance else None)
        if phone_number_value:
            self.fields["phone_number"].initial = phone_number_value

        # ✅ Required fields
        required_fields = [
            "first_name", "last_name", "address", "city", "state_province",
            "country", "postal", "email", "sin", "dob"
        ]
        for field in required_fields:
            self.fields[field].required = True

        self.fields["address_two"].required = False  # Optional field

        # ✅ Consistent Styling
        for field_name in self.fields:
            self.fields[field_name].widget.attrs["class"] = "mt-1 mb-2 form-control"

        # ✅ Crispy Forms Setup
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.add_input(Submit("submit", "Register"))
        self.helper.form_action = reverse_lazy("index")

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get("phone_number")
        if phone_number and CustomUser.objects.filter(phone_number=phone_number).exists():
            raise forms.ValidationError("This phone number is already in use.")
        return phone_number

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already in use.")
        return email

    def clean(self):
        cleaned_data = super().clean()
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
    """Form for inviting a new hire with a role selection."""

    class Meta:
        model = NewHireInvite
        fields = ["email", "name", "role"]
        widgets = {
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "Enter new hire's email"}),
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Full Name"}),
            "role": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        self.employer = kwargs.pop("employer", None)
        super().__init__(*args, **kwargs)

        # ✅ Dynamically set role choices
        self.fields["role"].choices = [
            ("Manager", "Manager"),
            ("GSA", "GSA"),
            ("CSR", "HR"),
        ]

    def clean_email(self):
        """Ensure the email isn't already invited and unused."""
        email = self.cleaned_data["email"].lower()
        if NewHireInvite.objects.filter(email=email, used=False).exists():
            raise forms.ValidationError("An invite for this email already exists.")
        return email

    def save(self, commit=True):
        """Ensure employer is assigned & token is generated if missing."""
        invite = super().save(commit=False)
        invite.employer = self.employer  # ✅ Assign employer automatically
        invite.token = invite.token or get_random_string(64)  # ✅ Generate token if missing

        if commit:
            invite.save()
        return invite

