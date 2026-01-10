from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from .models import Profile
from django.conf import settings

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Create profile after registering
    """
    if created:
        def create_profile():
            Profile.objects.create(user=instance)

        transaction.on_commit(create_profile)