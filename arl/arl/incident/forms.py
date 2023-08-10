from django import forms

from .models import Employer, Incident


class SectionOneForm(forms.ModelForm):
    class Meta:
        model = Incident
        fields = ['injuryorillness', 'environmental', 'regulatory', 'economicdamage',
                  'reputation', 'security', 'fire']
        widgets = {
            'injuryorillness': forms.CheckboxInput(),
            'environmental': forms.CheckboxInput(),
            'regulatory': forms.CheckboxInput(),
            'economicdamage': forms.CheckboxInput(),
            'reputation': forms.CheckboxInput(),
            'security': forms.CheckboxInput(),
            'fire': forms.CheckboxInput(),
        }


class SectionTwoForm(forms.ModelForm):
    class Meta:
        model = Incident
        fields = [
            'suncoremployee',
            'contractor',
            'associate',
            'generalpublic',
            'other',
            'othertext',
        ]
