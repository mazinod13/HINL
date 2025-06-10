from django import forms
from .models import Script

class ScriptForm(forms.ModelForm):
    class Meta:
        model = Script
        fields = ['symbol', 'script_name', 'sector']
        widgets = {
            'symbol': forms.TextInput(attrs={'class': 'form-control'}),
            'script_name': forms.TextInput(attrs={'class': 'form-control'}),
            'sector': forms.TextInput(attrs={'class': 'form-control'}),
        }

