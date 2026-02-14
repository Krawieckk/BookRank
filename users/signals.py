from django.db.models.signals import post_save, pre_save, post_delete
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

@receiver(pre_save, sender=Profile)
def delete_old_profile_picture_on_change(sender, instance: Profile, **kwargs):
    """
    Delete old profile picture from storage after changing
    """
    if not instance.pk:
        return 

    try:
        old = Profile.objects.get(pk=instance.pk)
    except Profile.DoesNotExist:
        return

    old_file = old.profile_picture
    new_file = instance.profile_picture

    if not old_file:
        return
    if old_file == new_file:
        return

    old_file.delete(save=False)


@receiver(post_delete, sender=Profile)
def delete_profile_picture_on_delete(sender, instance: Profile, **kwargs):
    """
    Delete profile picture from storage after deleting the profile
    """
    if instance.profile_picture:
        instance.profile_picture.delete(save=False)