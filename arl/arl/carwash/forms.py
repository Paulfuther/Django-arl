from django import forms
from .models import CarwashStatus
from arl.user.models import Store


class CarwashStatusForm(forms.ModelForm):
    class Meta:
        model = CarwashStatus
        fields = ['store', 'status', 'reason', 'date_time']

    def __init__(self, *args, **kwargs):
        # Extract the user from kwargs
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filter stores to only those with carwash=True
        if user and user.is_authenticated:
            self.fields['store'].queryset = Store.objects.filter(carwash=True)
        else:
            self.fields['store'].queryset = Store.objects.none()