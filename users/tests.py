from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from unittest.mock import patch
from django.contrib.auth.models import Group
from users.models import Profile

User = get_user_model()

# Create your tests here.
class CreateProfileSignalWorksTest(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create(username='user', password='pass12345', email='user@email.com')

    def test_profile_created_for_user(self):
        # Checks if the signal that crates the profile is working correctly
        self.assertTrue(Profile.objects.filter(user=self.user).exists())


class UpdateUsernameTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="oldname",
            password="pass12345",
            email="user@email.com"
        )
        self.url = reverse("update_username") 

    def test_logged_user_can_change_username(self):
        self.client.login(username="oldname", password="pass12345")

        resp = self.client.post(self.url, {"username": "newname"})

        self.assertEqual(resp.status_code, 200)

        self.user.refresh_from_db()

        self.assertEqual(self.user.username, "newname")
        self.assertEqual(resp.context["new_username"], "newname")

    def test_unauthenticated_user_cannot_access(self):
        resp = self.client.post(self.url, {"username": "newname"})

        self.assertEqual(resp.status_code, 302)

    def test_cannot_change_to_existing_username(self):
        User.objects.create_user(
            username="takenname",
            password="pass12345",
            email="taken@email.com"
        )

        self.client.login(username="oldname", password="pass12345")

        resp = self.client.post(self.url, {"username": "takenname"})

        self.assertEqual(resp.status_code, 200)

        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "oldname")

        form = resp.context["username_change_form"]
        self.assertTrue(form.errors)
