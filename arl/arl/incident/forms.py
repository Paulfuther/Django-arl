import random
import string

from django import forms
from django.utils.text import slugify

from .models import Incident, MajorIncident


class IncidentForm(forms.ModelForm):
    # user_employer = forms.ChoiceField(choices=[], required=False)
    image_folder = forms.CharField(widget=forms.TextInput(attrs={'style': 'display:none;'}))

    class Meta:
        model = Incident
        fields = "__all__"
        exclude = ['queued_for_sending', 'sent', 'sent_at']
        labels = {
            "syes": "Off Property Impact: Yes",
            "sno": "Off Property Impact: No",
            "scomment": "Comment",
            "othertext": "Comment",
            "ryes": "Regulatory Authorities Called: Yes",
            "rno": "Regulatory Authorities Called: No",
            "rna": "Does Not Apply",
            "rcomment": "Comment",
            "chemcomment": "Comment",
            "actionstaken": "Actions Taken",
            "correctiveactions": "Corrective Actions Taken",
            "volumerelease": "Volume Released",
            "sother": "Other: Yes",
            "s2comment": "Comment",
            "pyes": "Police Called: Yes",
            "pno": "Poice Called: No",
            "pna": "Does Not Apply",
            "pcase": "Police Report Number",
            "stolentransactions": "Stolen Transactions",
            "stoltransactions": "Dollar Amount of Stolen Product",
            "stolencards": "Stolen Cards",
            "stolcards": "Dollar Amount of Stolen Cards",
            "stolentobacco": "Stolen Tobacco",
            "stoltobacco": "Dollar Amount of Stolen Tobacco",
            "stolenlottery": "Stolen Lottery",
            "stollottery": "Dollar Amount of Stolen Lottery",
            "stolenfuel": "Stolen Fuel",
            "stolfuel": "Dollar Amount of Stolen Fuel",
            "stolenother": "Other",
            "stolother": "Description of Other",
            "stolenothervalue": "Dollar Amount of Other",
            "stolenna": "Information Not Available",
        }
        widgets = {
            "causalfactors": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Enter any unplanned, unintended contributor to the incident, that if eliminated would have either prevented the occurrence of the incident or reduced its severity or frequency: (i.e. fatigue, acts of nature, improper lifting, removed guard, following too closely, etc.) What equipment/tools were not available or failed? Were there any workarounds from the normal process? What training did you receive to complete the task?",
                    "style": "font-weight:300; font-style:italic; color:#666;",
                }
            ),
            "determincauses": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Understand what happened, including any weaknesses in the process. Do not accept human error as the single cause of the event. Think about the most basic reason and primary driver the incident took place. Consider root cause by using methods such as 5-Why.",
                    "style": "font-weight:300; font-style:italic; color:#666;",
                }
            ),
            "preventiveactions": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Describe the actions or changes that will be made to prevent the same or a similar incident from occurring in the future. Will the action(s) prevent, or significantly reduce the likelihood of, the incident from reoccurring? If the answer is ”No”, revisit the investigation. Ask the worker/victim – what do we need to ensure this incident does not happen again? What safeguard(s) should be in place to allow you to fail safely? Consider recurring hazards. What controls are available to prevent you from being seriously injured? Were they effective? How can we make them more effective?",
                    "style": "font-weight:300; font-style:italic; color:#666;",
                }
            ),
            "eventtimeline": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "What happened? Please provide the event facts in a detailed timeline.",
                    "style": "font-weight:300; font-style:italic; color:#666;",
                }
            ),
        }

    eventdate = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    eventtime = forms.TimeField(widget=forms.TimeInput(attrs={"type": "time"}))

    def generate_random_folder(self):
        return "".join(random.choices(string.ascii_letters + string.digits,
                                      k=10))

    def create_folder(self, instance):
        if not instance.image_folder:
            # Generate a slug from a descriptive field in your model
            # (e.g., title)
            slug = slugify(instance.brief_description)[:50]  # Limit the slug
            # length
            # Generate a random string for additional uniqueness
            random_string = self.generate_random_folder()
            # Combine the slug and random string to create a folder name
            folder_name = f"{slug}-{random_string}"
            # Set the folder name as the initial value for the image_folder
            # field
            instance.image_folder = folder_name

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)  # Get the user from the kwargs
        super().__init__(*args, **kwargs)

        # Check if it's a new form (not an update)
        if self.instance.pk is None:
            # Set the initial value for image_folder
            self.create_folder(self.instance)
            self.fields["image_folder"].initial = self.instance.image_folder

        if user:
            self.fields["user_employer"].initial = self.get_user_employer(user)
            # Disable the user_employer field and set its initial value
            self.fields['user_employer'].disabled = True
            #self.fields['user_employer'].initial = self.get_user_employer(user)
            #self.fields['user_employer'].widget.attrs['disabled'] = 'disabled'

    def get_user_employer(self, user):
        employer = user.employer
        return employer


class MajorIncidentForm(forms.ModelForm):
    # user_employer = forms.ChoiceField(choices=[], required=False)
    image_folder = forms.CharField(widget=forms.TextInput(attrs={'style': 'display:none;'}))

    class Meta:
        model = MajorIncident
        fields = "__all__"
        labels = {
            "policeagency": "Police Agency (eg. RCMP, OPP, etc)",
            "officerdetails": "Name Rank Badge etc.",
            "policecalledyes": "Police Called: Yes",
            "policecalledno": "Poice Called: No",
            "policeattendyes": "Police Attend Yes",
            "policeattendno": "Police Attend No",
            "policefilenumber": "Police File Number",
            "gsoccalledyes": "GSOC called Yes",
            "gsoccalledno": "GSOC called no",
            "stolentransactions": "Stolen Transactions",
            "stoltransactions": "Dollar Amount of Stolen Product",
            "stolencards": "Stolen Cards",
            "stolcards": "Dollar Amount of Stolen Cards",
            "stolentobacco": "Stolen Tobacco",
            "stoltobacco": "Dollar Amount of Stolen Tobacco",
            "stolenlottery": "Stolen Lottery",
            "stollottery": "Dollar Amount of Stolen Lottery",
            "stolenfuel": "Stolen Fuel",
            "stolfuel": "Dollar Amount of Stolen Fuel",
            "stolenother": "Other",
            "stolother": "Description and Value of Other",
            "stolenna": "N/A Information Not Available",
            "distinguishablefeatures": "Distinguishable Features",
            "licenceplatenumber": "Licence Plate Number",
            "approximateyearmakemodel": "Approximate Year, Make & Model",
            "direction": "Direction of Travel",
            "bumpersticker": "Bumper Sticker",
            "damagetoproperty": "Damage details and value",
            "eyeeyeglasses": "Eye Colour/ Glasses",
        }

    eventdate = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    eventtime = forms.TimeField(widget=forms.TimeInput(attrs={"type": "time"}))

    def generate_random_folder(self):
        return "".join(random.choices(string.ascii_letters + string.digits,
                                      k=10))

    def create_folder(self, instance):
        if not instance.image_folder:
            # Generate a slug from a descriptive field in your model
            # (e.g., title)
            slug = slugify(instance.brief_description)[:50]  # Limit the slug
            # length
            # Generate a random string for additional uniqueness
            random_string = self.generate_random_folder()
            # Combine the slug and random string to create a folder name
            folder_name = f"{slug}-{random_string}"
            # Set the folder name as the initial value for the image_folder
            # field
            instance.image_folder = folder_name

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)  # Get the user from the kwargs
        super().__init__(*args, **kwargs)

        # Check if it's a new form (not an update)
        if self.instance.pk is None:
            # Set the initial value for image_folder
            self.create_folder(self.instance)
            self.fields["image_folder"].initial = self.instance.image_folder

        if user:
            self.fields["user_employer"].initial = self.get_user_employer(user)
            # Disable the user_employer field and set its initial value
            self.fields['user_employer'].disabled = True
            #self.fields['user_employer'].initial = self.get_user_employer(user)
            #self.fields['user_employer'].widget.attrs['disabled'] = 'disabled'

    def get_user_employer(self, user):
        employer = user.employer
        return employer
