import random
import string
from django.utils import timezone
from django import forms
from django.forms import inlineformset_factory
from django.utils.text import slugify
import pytz

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

    date_salted = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), disabled=True)
    time_salted = forms.TimeField(widget=forms.TimeInput(attrs={"type": "time"}), disabled=True)

    class Meta:
        model = SaltLog
        fields = "__all__"

    def generate_random_folder(self):
        return "".join(random.choices(string.ascii_letters + string.digits, k=10))

    def create_folder(self, instance):
        if not instance.image_folder:
            slug = slugify(instance.area_salted)[:50]
            random_string = self.generate_random_folder()
            folder_name = f"{slug}-{random_string}"
            instance.image_folder = folder_name

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        # Set date_salted and time_salted to the current date and time, and disable them
        if self.instance.pk is None:  # Only set these for new entries
            current_datetime = timezone.now().astimezone(pytz.timezone("America/New_York"))
            self.fields["date_salted"].initial = current_datetime.date()
            self.fields["time_salted"].initial = current_datetime.time()

            # Set initial value for image_folder if it’s a new entry
            self.create_folder(self.instance)
            self.fields["image_folder"].initial = self.instance.image_folder
            self.instance.user = user  # Set user on instance directly

        if user:
            self.fields["user_employer"].initial = self.get_user_employer(user)
            self.fields['user_employer'].disabled = True

    def get_user_employer(self, user):
        return user.employer
