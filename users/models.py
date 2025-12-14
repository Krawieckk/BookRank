from django.db import models
from django.contrib.auth import get_user_model

# Create your models here.
class Profile(models.Model):
    user = models.OneToOneField(get_user_model(), 
                                   on_delete=models.CASCADE, 
                                   related_name='profile')
    profile_picture = models.ImageField(
        upload_to='avatars/', 
        blank=True, 
        default='avatars/default.png'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f'Profile({self.user})'
