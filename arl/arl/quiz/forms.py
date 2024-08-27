from django import forms
from django.forms import inlineformset_factory
from .models import Quiz, Question, Answer


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
