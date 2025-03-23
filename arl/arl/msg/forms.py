from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms
from django.contrib.auth.models import Group
from arl.user.models import CustomUser, Store
from django.db import models
from arl.msg.models import EmailTemplate, WhatsAppTemplate
from django.contrib.auth import get_user_model


User = get_user_model()


class SMSForm(forms.Form):
    message = forms.CharField(
        max_length=1000,
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": "Enter a message (max 1000 characters)",
                "class": "custom-input",
            }
        ),
        help_text="",
    )

    selected_group = forms.ModelChoiceField(
        queryset=Group.objects.none(),  # Set dynamically in __init__
        required=True,
        label="Select Group to Send SMS",
        widget=forms.Select(attrs={"class": "custom-input"}),
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)  # Get the logged-in user
        super().__init__(*args, **kwargs)

        if user and user.employer:
            employer = user.employer
            self.fields["selected_group"].queryset = Group.objects.filter(user__employer=employer).distinct()

        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.add_input(Submit("submit", "Submit"))


class TemplateEmailForm(forms.Form):
    sendgrid_id = forms.ModelMultipleChoiceField(
        queryset=EmailTemplate.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label="Select Template",
    )
    selected_group = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Select Groups",
    )
    selected_users = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Select Active Users",
    )

    attachment_1 = forms.FileField(required=False, label="Attachment 1")
    attachment_2 = forms.FileField(required=False, label="Attachment 2")
    attachment_3 = forms.FileField(required=False, label="Attachment 3")

    def __init__(self, *args, **kwargs):
        """Filter email templates based on employer."""
        user = kwargs.pop("user", None)  # ✅ Get user from kwargs
        super().__init__(*args, **kwargs)

        if user and hasattr(user, "employer"):  # ✅ Ensure user has employer field
            employer = user.employer
            self.fields["sendgrid_id"].queryset = EmailTemplate.objects.filter(
                models.Q(employers=employer) | models.Q(employers__isnull=True)
            ).distinct()
            
        # ✅ Filter `selected_users` to include only users from the same employer
            self.fields["selected_users"].queryset = User.objects.filter(
                employer=employer, is_active=True
            )

    def clean(self):
        cleaned_data = super().clean()
        selected_group = cleaned_data.get("selected_group")
        selected_users = cleaned_data.get("selected_users")

        # Ensure at least one is selected, but not both
        if not selected_group and not selected_users:
            raise forms.ValidationError("You must select "
                                        "either a group or at least one user.")
        if selected_group and selected_users:
            raise forms.ValidationError("You cannot select "
                                        "both a group and individual users.")

        return cleaned_data


class TemplateWhatsAppForm(forms.Form):
    whatsapp_id = forms.ModelChoiceField(
        queryset=WhatsAppTemplate.objects.all(), label="Select Template"
    )

    selected_group = forms.ModelChoiceField(
        queryset=Group.objects.all(),
        required=True,
        label="Select Group to Send Whatsapp",
        widget=forms.Select(attrs={"class": "custom-input"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name != 'csrfmiddlewaretoken':  # Skip CSRF token field
                field.widget.attrs.update({'class': 'custom-input'})


class SendGridFilterForm(forms.Form):
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type':
                                      'date', 'class': 'form-control'}),
        label="From"
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type':
                                      'date', 'class': 'form-control'}),
        label="To"
    )
    template_id = forms.ModelChoiceField(
        queryset=EmailTemplate.objects.all(),
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Template Name"
    )


class TemplateFilterForm(forms.Form):
    template_id = forms.ModelChoiceField(
        queryset=EmailTemplate.objects.all(),
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Template Name"
    )
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type":
                                      "date", "class": "form-control"}),
        label="Start Date"
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type":
                                      "date", "class": "form-control"}),
        label="End Date"
    )


class CampaignSetupForm(forms.Form):
    contact_list = forms.ChoiceField(
        label="Select Contact List",
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    def __init__(self, *args, **kwargs):
        contact_list_choices = kwargs.pop("contact_list_choices", [])
        super().__init__(*args, **kwargs)
        self.fields["contact_list"].choices = contact_list_choices


class EmployeeSearchForm(forms.Form):
    employee = forms.ModelChoiceField(
        queryset=CustomUser.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Select Employee"
    )


# Form for selecting a group
class GroupSelectForm(forms.Form):
    group = forms.ModelChoiceField(queryset=Group.objects.all(),
                                   required=True, label="Select Group")


class StoreTargetForm(forms.ModelForm):
    sales_target = forms.IntegerField(required=True, label='Sales Target')

    class Meta:
        model = Store
        fields = ['number', 'sales_target']

    def __init__(self, *args, **kwargs):
        super(StoreTargetForm, self).__init__(*args, **kwargs)
        self.fields['number'].disabled = True
        self.fields['number'].label = "Store Number"
