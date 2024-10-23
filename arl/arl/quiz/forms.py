import random
import string

from django import forms
from django.forms import inlineformset_factory
from django.forms.widgets import SelectDateWidget, TimeInput
from django.utils import timezone
from django.utils.text import slugify

from .models import Answer, Question, Quiz, SaltLog


class QuizForm(forms.ModelForm):
    class Meta:
        model = Quiz
        fields = ['title', 'description']


class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ['text']


class AnswerForm(forms.ModelForm):
    class Meta:
        model = Answer
        fields = ['text', 'is_correct']

# Inline formsets for dynamic forms


QuestionFormSet = inlineformset_factory(Quiz, Question,
                                        form=QuestionForm, extra=1,
                                        can_delete=True,)
AnswerFormSet = inlineformset_factory(Question, Answer,
                                      form=AnswerForm, extra=1,
                                      can_delete=True)


class SaltLogForm(forms.ModelForm):
    image_folder = forms.CharField(widget=forms.TextInput(attrs={'style': 'display:none;'}))

    class Meta:
        model = SaltLog
        fields = "__all__"

    date_salted = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}
                                                         ))
    time_salted = forms.TimeField(widget=forms.TimeInput(attrs={"type": "time"}
                                                         ))

    def generate_random_folder(self):
        return "".join(random.choices(string.ascii_letters + string.digits,
                                      k=10))

    def create_folder(self, instance):
        if not instance.image_folder:
            # Generate a slug from a descriptive field in your model
            slug = slugify(instance.area_salted)[:50]  # Limit slug length
            # Generate a random string for additional uniqueness
            random_string = self.generate_random_folder()
            # Combine the slug and random string to create a folder name
            folder_name = f"{slug}-{random_string}"
            # Set the folder name as the initial value for the image_folder field
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

    def get_user_employer(self, user):
        employer = user.employer
        return employer

