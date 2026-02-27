from django.contrib.auth.forms import UserCreationForm, PasswordResetForm, PasswordChangeForm
from django import forms
from django.contrib.auth import get_user_model
from django.template import loader
from .tasks import send_email_task
from .models import Profile
from django.core.validators import FileExtensionValidator
from PIL import Image, ImageOps
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile
from io import BytesIO
import os
from uuid import uuid4

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

class UsernameUpdateForm(forms.ModelForm):
    class Meta:
        model = get_user_model()
        fields = ['username']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance.pk:
            current_username = self.instance.username

            self.initial['username'] = ''

            self.fields['username'].widget.attrs.update({
                'placeholder': current_username, 
                'class': 'w-full border px-2 py-1',
                'id': 'id_username_helptext',
            })


class CustomPasswordUpdateForm(PasswordChangeForm):
    class Meta:
        fields = ['old_password', 'new_password1', 'new_password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.widget.attrs.update({
                'class': 'w-full border px-2 py-1'
            })

        self.fields['old_password'].widget.attrs.update({
            'autocomplete': 'current-password'
        })
        self.fields['new_password1'].widget.attrs.update({
            'autocomplete': 'new-password', 
            'id': 'id_new_password1_helptext'
        })
        self.fields['new_password2'].widget.attrs.update({
            'autocomplete': 'new-password', 
            'id': 'id_new_password2_helptext'
        })
        
class ProfilePictureChangeForm(forms.ModelForm):
    MAX_SIZE = 3 * 1024 * 1024
    AVATAR_SIZE = 300

    class Meta:
        model = Profile
        fields = ['profile_picture']
        widgets = {
            "profile_picture": forms.FileInput(
                attrs={
                    "class": "text-sm py-1 px-2 border",
                    "accept": "image/jpeg, image/png"
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['profile_picture'].validators.append(
            FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png'])
        )

    def clean_profile_picture(self):
        file = self.cleaned_data.get("profile_picture")

        if not file:
            return file
        
        if file.size > self.MAX_SIZE:
            raise ValidationError("File is too large (max 3MB).")

        try:
            img = Image.open(file)
            img.verify()
        except Exception:
            raise ValidationError("Uploaded file is not a valid image.")

        try:
            file.seek(0)
        except Exception:
            pass

        return file

    def save(self, commit=True):
        instance = super().save(commit=False)
        file = self.cleaned_data.get("profile_picture")

        if file:
            img = Image.open(file)

            img = ImageOps.exif_transpose(img)

            width, height = img.size
            min_side = min(width, height)

            left = (width - min_side) / 2
            top = (height - min_side) / 2
            right = (width + min_side) / 2
            bottom = (height + min_side) / 2

            img = img.crop((left, top, right, bottom))
            img = img.resize((self.AVATAR_SIZE, self.AVATAR_SIZE), Image.LANCZOS)

            fmt = (img.format or "").upper()
            if fmt == "JPG":
                fmt = "JPEG"
            if fmt not in {"JPEG", "PNG"}:
                fmt = "JPEG"

            if fmt == "JPEG" and img.mode in ("RGBA", "LA"):
                img = img.convert("RGB")

            buffer = BytesIO()

            save_kwargs = {}
            if fmt == "JPEG":
                save_kwargs = {"quality": 90, "optimize": True}
            elif fmt == "PNG":
                save_kwargs = {"optimize": True}

            img.save(buffer, format=fmt, **save_kwargs)
            buffer.seek(0)

            ext_map = {"JPEG": ".jpg", "PNG": ".png"}
            base = os.path.splitext(file.name)[0]
            new_name = f"avatar_{uuid4().hex}{ext_map[fmt]}"

            resized_file = InMemoryUploadedFile(
                file=buffer,
                field_name="profile_picture",
                name=new_name,
                content_type=file.content_type,
                size=buffer.getbuffer().nbytes,
                charset=None
            )

            instance.profile_picture = resized_file

        if commit:
            instance.save()

        return instance
