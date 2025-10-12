from crispy_forms.helper import FormHelper
from crispy_forms.layout import HTML, Div, Field, Layout, Submit
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.validators import (
    MaxLengthValidator,
    MinLengthValidator,
    RegexValidator,
)
from django.urls import reverse_lazy
from django.utils.crypto import get_random_string

from .models import CustomUser, Employer, NewHireInvite, Store
from arl.user.services import set_user_sin


class CustomUserCreationForm(UserCreationForm):
    # WRITE-ONLY SIN FIELD (not bound to model)
    sin_input = forms.CharField(
        label="SIN (9 digits)",
        required=True,
        validators=[
            MinLengthValidator(9),
            MaxLengthValidator(9),
            RegexValidator(r"^\d{9}$", "SIN number must be 9 digits"),
        ],
        widget=forms.TextInput(attrs={"autocomplete": "off"}),
    )

    store = forms.ModelChoiceField(
        queryset=Store.objects.none(),
        required=False,  # ✅ Make store optional for employers
        widget=forms.Select(attrs={"class": "form-control"}),
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
            "sin_input",
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
            "dob": forms.DateInput(attrs={"type": "date"}),
            "sin_expiration_date": forms.DateInput(attrs={"type": "date"}),
            "work_permit_expiration_date": forms.DateInput(attrs={"type": "date"}),
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
                self.fields["store"].widget.attrs["disabled"] = (
                    "disabled"  # Prevent selection
                )
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
        phone_number_value = self.data.get("phone_number") or (
            self.instance.phone_number if self.instance else None
        )
        if phone_number_value:
            self.fields["phone_number"].initial = phone_number_value

        # ✅ Required fields
        required_fields = [
            "first_name",
            "last_name",
            "address",
            "city",
            "state_province",
            "country",
            "postal",
            "email",
            "sin_input",
            "dob",
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
        if (
            phone_number
            and CustomUser.objects.filter(phone_number=phone_number).exists()
        ):
            raise forms.ValidationError("This phone number is already in use.")
        return phone_number

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already in use.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        sin = cleaned_data.get("sin_input")
        sin_expiration_date = cleaned_data.get("sin_expiration_date")
        work_permit_expiration_date = cleaned_data.get("work_permit_expiration_date")

        if sin and sin.startswith("9"):
            if not sin_expiration_date:
                self.add_error(
                    "sin_expiration_date",
                    "SIN expiration date is required for SINs starting with 9.",
                )
            if not work_permit_expiration_date:
                self.add_error(
                    "work_permit_expiration_date",
                    "Work permit expiration date is required for SINs starting with 9.",
                )

        return cleaned_data

    def save(self, commit=True):
        """
        Create the user, then encrypt & store the SIN into
        sin_encrypted/sin_last4/sin_hash. Never save plaintext.
        """
        user = super().save(commit=False)

        # Ensure employer/store disabled field doesn't block save
        if self.fields["store"].widget.attrs.get("disabled"):
            user.store = None

        if commit:
            user.save()

        return user
    

class TwoFactorAuthenticationForm(forms.Form):
    verification_code = forms.CharField(
        max_length=12,
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    def __init__(self, *args, **kwargs):
        super(TwoFactorAuthenticationForm, self).__init__(*args, **kwargs)
        self.fields["verification_code"].widget.attrs.update(
            {"style": "margin: 10px 0;"}
        )


class NewHireInviteForm(forms.ModelForm):
    """Form for inviting a new hire with a role selection."""

    # Optional inputs for who left
    departed_name = forms.CharField(
        required=False,
        label="Departing Employee Name",
        widget=forms.TextInput(
            attrs={
                "class": "form-control mb-2 placeholder-light",
                "placeholder": "If replacing someone, enter their name",
            }
        ),
    )
    departed_email = forms.EmailField(
        required=False,
        label="Departing Employee Email",
        widget=forms.EmailInput(
            attrs={
                "class": "form-control mb-2 placeholder-light",
                "placeholder": "If replacing someone, enter their email",
            }
        ),
    )

    class Meta:
        model = NewHireInvite
        fields = ["email", "name", "role"]
        widgets = {
            "email": forms.EmailInput(
                attrs={
                    "class": "form-control placeholder-light",
                    "placeholder": "Enter new hire's email",
                }
            ),
            "name": forms.TextInput(
                attrs={
                    "class": "form-control placeholder-light",
                    "placeholder": "Full Name",
                }
            ),
            "role": forms.Select(attrs={"class": "form-control mb-4"}),
        }

    def __init__(self, *args, **kwargs):
        self.employer = kwargs.pop("employer", None)
        self.invited_by = kwargs.pop("invited_by", None)
        super().__init__(*args, **kwargs)

        # ✅ Dynamically set role choices
        self.fields["role"].choices = [
            ("Manager", "Manager"),
            ("GSA", "GSA"),
            ("CSR", "HR"),
        ]

        self.helper = FormHelper()
        self.helper.layout = Layout(
            "email",
            "name",
            "role",
            Div(
                HTML("<hr><h6 class='mt-3'>Optional: Who is this replacing?</h6>"),
                Field("departed_name", wrapper_class="mb-2"),
                Field("departed_email"),
                css_class="p-3 border rounded bg-light mt-3",
            ),
        )

    def clean_email(self):
        """Ensure the email isn't already invited and unused."""
        email = self.cleaned_data["email"].lower()
        if NewHireInvite.objects.filter(email=email, used=False).exists():
            raise forms.ValidationError("An invite for this email already exists.")
        return email

    def save(self, commit=True):
        """Ensure employer is assigned & token is generated if missing."""
        invite = super().save(commit=False)
        invite.employer = self.employer
        if self.invited_by:
            invite.invited_by = self.invited_by  # ✅ Assign employer automatically
        invite.token = invite.token or get_random_string(
            64
        )  # ✅ Generate token if missing

        if commit:
            invite.save()
        return invite
