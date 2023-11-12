import random
import string

from django import forms
from django.utils.text import slugify

from .models import Incident


class IncidentForm(forms.ModelForm):
    #user_employer = forms.ChoiceField(choices=[], required=False)
    image_folder = forms.CharField(widget=forms.TextInput(attrs={'style': 'display:none;'}))
    class Meta:
        model = Incident
        fields = "__all__"
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
