from phonenumber_field.formfields import PhoneNumberField
from django import forms
from .models import Employer, EmployerRequest


class EmployerRegistrationForm(forms.ModelForm):
    """Form for new employers to request access."""

    senior_contact_name = forms.CharField(
        max_length=255,
        required=True,
        label="Senior Contact Name",
        help_text="Who is responsible for employee onboarding?",
    )
    phone_number = PhoneNumberField(required=True, label="Contact Phone Number")
    verified_sender_local = forms.CharField(
        max_length=50,
        required=True,
        label="Verified Email (Local Part)",
        help_text="Enter only the part before '@1553690ontarioinc.com'",
    )

    widgets = {
        "company_name": forms.TextInput(attrs={"placeholder": "Acme Inc."}),
        "email": forms.EmailInput(attrs={"placeholder": "email@example.com"}),
        "phone_number": forms.TextInput(attrs={"placeholder": "123-456-7890"}),
        "senior_contact_first_name": forms.TextInput(attrs={"placeholder": "John"}),
        "senior_contact_last_name": forms.TextInput(attrs={"placeholder": "Doe"}),
    }

    class Meta:
        model = EmployerRequest
        fields = [
            "company_name",
            "email",
            "address",
            "address_two",
            "city",
            "state_province",
            "country",
            "phone_number",
            "senior_contact_first_name",
            "senior_contact_last_name",
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
