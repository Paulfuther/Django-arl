from django import forms
from .models import RecruitApplicant


class RecruitApplicantForm(forms.ModelForm):
    resume = forms.FileField(required=False)

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
            "availability": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({"class": "form-check-input"})
            else:
                field.widget.attrs.update({"class": "form-control"})

        self.fields["first_name"].widget.attrs.update({"placeholder": "First name"})
        self.fields["last_name"].widget.attrs.update({"placeholder": "Last name"})
        self.fields["email"].widget.attrs.update({"placeholder": "Email address"})
        self.fields["phone_number"].widget.attrs.update({"placeholder": "Phone number"})
        self.fields["city"].widget.attrs.update({"placeholder": "City"})
        self.fields["position_interest"].widget.attrs.update(
            {"placeholder": "Position you are interested in"}
        )
        self.fields["linkedin_profile"].widget.attrs.update(
            {"placeholder": "Optional LinkedIn profile URL"}
        )

        self.fields["resume"].widget.attrs.update({"class": "form-control"})

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
                raise forms.ValidationError("File size must be under 5MB.")

        return resume