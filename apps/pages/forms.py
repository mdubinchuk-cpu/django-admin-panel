from django import forms
from .models import Product  # Импорт модели (убедись, что models.py существует с Product)

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'info', 'price']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'info': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }