from django.db import models

from arl.user.models import Employer


class Quiz(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class Question(models.Model):
    quiz = models.ForeignKey(Quiz, related_name='questions',
                             on_delete=models.CASCADE)
    text = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.text


class Answer(models.Model):
    question = models.ForeignKey(Question, related_name='answers',
                                 on_delete=models.CASCADE)
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return self.text


class SaltLog(models.Model):
    store = models.ForeignKey('user.Store', on_delete=models.CASCADE)
    area_salted = models.CharField(max_length=255)
    date_salted = models.DateField(null=True)
    time_salted = models.TimeField(null=True)  # Add time field
    hidden_timestamp = models.DateTimeField(auto_now_add=True)
    image_folder = models.CharField(max_length=255, null=True)
    user_employer = models.ForeignKey(Employer, on_delete=models.SET_NULL,
                                      null=True)

    def __str__(self):
        return f"Salt Log {self.pk}"
