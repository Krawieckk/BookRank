from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser

# Create your models here.
class CustomUser(AbstractUser):
    email = models.EmailField(blank=False, unique=True)

    def __str__(self):
        return self.username

class Profile(models.Model):
    user = models.OneToOneField(get_user_model(), 
                                   on_delete=models.CASCADE, 
                                   related_name='profile')
    profile_picture = models.ImageField(
        upload_to='avatars/', 
        blank=True, 
        default='avatars/profile-picture.png'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f'Profile({self.user})'
