from django.contrib.auth.forms import UserCreationForm
from django import forms
from django.contrib.auth import get_user_model

class RegisterForm(UserCreationForm):
    class Meta:
        model = get_user_model()
        # 'password1' i 'password2' są obsługiwane automatycznie przez UserCreationForm,
        # ale warto dodać 'email' do listy pól, aby był widoczny w formularzu.
        fields = ['username', 'email']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Twoja pętla stylizująca (Tailwind/CSS) pozostaje bez zmian
        for field in self.fields.values():
            field.widget.attrs.update({
                'class': 'w-full border px-2 py-1'
            })

class LoginForm(forms.Form):
    username = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.widget.attrs.update({
                'class': 'w-full border px-2 py-1'
            })

