from django import forms
from phonenumbers import (
    NumberParseException,
    PhoneNumberFormat,
    format_number,
    is_valid_number,
    parse,
)

from .models import RecruitApplicant


class RecruitApplicantForm(forms.ModelForm):
    resume = forms.FileField(required=False)
    spam_check = forms.CharField(required=False)

    class Meta:
        model = RecruitApplicant
        fields = [
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "city",
            "position_interest",
            "employment_type",
            "availability",
            "has_transportation",
            "eligible_to_work_in_canada",
            "linkedin_profile",
        ]
        widgets = {
            "availability": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Please let us know what days or times you are available to work.",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Apply Bootstrap classes
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({"class": "form-check-input"})
            else:
                existing_class = field.widget.attrs.get("class", "")
                field.widget.attrs.update(
                    {"class": f"{existing_class} form-control".strip()}
                )

        # Friendly placeholders
        self.fields["first_name"].widget.attrs.update(
            {"placeholder": "Enter your first name"}
        )
        self.fields["last_name"].widget.attrs.update(
            {"placeholder": "Enter your last name"}
        )
        self.fields["email"].widget.attrs.update(
            {"placeholder": "Enter your email address"}
        )
        self.fields["phone_number"].widget.attrs.update(
            {"placeholder": "e.g. 519-555-1234"}
        )
        self.fields["city"].widget.attrs.update({"placeholder": "Enter your city"})
        
        self.fields["position_interest"].widget.attrs.update(
            {"placeholder": "What position are you interested in?"}
        )
        self.fields["linkedin_profile"].widget.attrs.update(
            {"placeholder": "Optional LinkedIn profile URL"}
        )

        # Resume field styling/help
        self.fields["resume"].widget.attrs.update({"class": "form-control"})
        self.fields["resume"].help_text = "Accepted formats: PDF, DOC, DOCX. Maximum size: 5MB."

    def clean_phone_number(self):
        phone = self.cleaned_data.get("phone_number", "").strip()

        try:
            parsed = parse(phone, "CA")

            if not is_valid_number(parsed):
                raise forms.ValidationError(
                    "Enter a valid Canada or US phone number."
                )

            return format_number(parsed, PhoneNumberFormat.E164)

        except NumberParseException:
            raise forms.ValidationError(
                "Enter a valid Canada or US phone number."
            )

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("spam_check"):
            raise forms.ValidationError("Invalid submission.")

        return cleaned_data

    def clean_resume(self):
        resume = self.cleaned_data.get("resume")

        if resume:
            allowed_extensions = [".pdf", ".doc", ".docx"]
            filename = resume.name.lower()

            if not any(filename.endswith(ext) for ext in allowed_extensions):
                raise forms.ValidationError(
                    "Resume must be a PDF, DOC, or DOCX file."
                )

            if resume.size > 5 * 1024 * 1024:
                raise forms.ValidationError(
                    "Resume file size must be under 5MB."
                )

        return resume
