from django.contrib.auth.forms import UserCreationForm, PasswordResetForm
from django import forms
from django.contrib.auth import get_user_model

from django.core.mail import EmailMultiAlternatives
from django.template import loader
from django.utils.html import strip_tags
from .tasks import send_email_task

class RegisterForm(UserCreationForm):
    class Meta:
        model = get_user_model()
        fields = ['username', 'email']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
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


class AsyncPasswordResetForm(PasswordResetForm):
    """
    reset password sent asynchronously using celery
    """

    def send_mail(
        self,
        subject_template_name,
        email_template_name,
        context,
        from_email,
        to_email,
        html_email_template_name=None,
    ):
        subject = loader.render_to_string(subject_template_name, context).strip()
        body = loader.render_to_string(email_template_name, context)

        html_body = None
        if html_email_template_name:
            html_body = loader.render_to_string(html_email_template_name, context)

        # Celery task
        send_email_task.delay(
            subject=subject,
            body=body,
            from_email=from_email,
            to=[to_email],
            html_body=html_body
        )