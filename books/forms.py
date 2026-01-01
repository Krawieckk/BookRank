from django.forms import ModelForm
from .models import Review
from django import forms

class ReviewForm(ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'review_text']

        widgets = {
            "rating": forms.Select(attrs={
                "class": (
                    "w-full rounded-sm border border-slate-400 bg-white px-3 py-2 text-sm focus:border-slate-600 focus:ring-0"
                )
            }),
            "review_text": forms.Textarea(attrs={
                "class": (
                    "w-full rounded-sm border border-slate-400 bg-white px-3 py-3 text-sm "
                    "focus:border-slate-600 focus:ring-0"
                ),
                "rows": 8,
                "placeholder": "Text",
            }),
        }