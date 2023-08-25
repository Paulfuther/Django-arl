from django import forms
from django.forms import HiddenInput, CharField

from .models import Incident


class IncidentForm(forms.ModelForm):
    class Meta:
        model = Incident
        fields = '__all__'
        image_folder = CharField(widget=HiddenInput(), required=False)
        widgets = {
            'user_employer': forms.HiddenInput(),
        }
        labels = {
            'syes': 'Off Property Impact: Yes',
            'sno': 'Off Property Impact: No',
            'scomment': 'Comment',
            'othertext': 'Comment',
            'ryes': 'Regulatory Authorities Called: Yes',
            'rno': 'Regulatory Authorities Called: No',
            'rna': 'Does Not Apply',
            'rcomment': 'Comment',
            'chemcomment': 'Comment',
            'actionstaken': 'Actions Taken',
            'correctiveactions': 'Corrective Actions Taken',
            'volumerelease': 'Volume Released',
            'sother': 'Other: Yes',
            's2comment': 'Comment',
            'pyes': 'Police Called: Yes',
            'pno': 'Poice Called: No',
            'pna': 'Does Not Apply',
            'pcase': 'Police Report Number',
            'stolentransactions': 'Stolen Transactions',
            'stoltransactions': 'Dollar Amount of Stolen Product',
            'stolencards': 'Stolen Cards',
            'stolcards': 'Dollar Amount of Stolen Cards',
            'stolentobacco': 'Stolen Tobacco',
            'stoltobacco': 'Dollar Amount of Stolen Tobacco',
            'stolenlottery': 'Stolen Lottery',
            'stollottery': 'Dollar Amount of Stolen Lottery',
            'stolenfuel': 'Stolen Fuel',
            'stolfuel': 'Dollar Amount of Stolen Fuel',
            'stolenother': 'Other',
            'stolother': 'Description of Other',
            'stolenothervalue': 'Dollar Amount of Other',
            'stolenna': 'Information Not Available',
        }
    eventdate = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    eventtime = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time'}))
    image_folder = CharField(widget=HiddenInput(), required=False)
