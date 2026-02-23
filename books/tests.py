from django.test import TestCase, TransactionTestCase
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.urls import reverse
from unittest.mock import patch
from django.contrib.auth.models import Group
from books.models import Book, Review, ReviewSummary

User = get_user_model()

# Create your tests here.
class BookRatingTests(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="user1", password="pass12345", email="example@email.com")
        self.book = Book.objects.create(title="Test Book")
        self.rs = ReviewSummary.objects.create(book=self.book)

    def _login_user(self):
        self.client.login(username="user1", password="pass12345")

    def test_average_rating_after_adding_reviews(self):
        Review.objects.create(book=self.book, user=self.user, rating=5, review_text="ok")
        Review.objects.create(book=self.book, user=self.user, rating=2, review_text="ok2")

        self.book.refresh_from_db()

        self.assertEqual(self.book.reviews_count, 2)
        self.assertEqual(self.book.average_rating, Decimal("3.50"))

    def test_average_rating_after_deleting_review(self):
        r1 = Review.objects.create(book=self.book, user=self.user, rating=5, review_text="ok")
        Review.objects.create(book=self.book, user=self.user, rating=1, review_text="ok2")

        r1.delete()

        self.book.refresh_from_db()

        self.assertEqual(self.book.reviews_count, 1)
        self.assertEqual(self.book.average_rating, Decimal("1.00"))


class AuthorizationTests(TransactionTestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username="user1", password="pass12345", email='user1@email.com')
        self.user2 = User.objects.create_user(username='user2', password="pass12345", email='user2@email.com')
        self.book = Book.objects.create(title="Test Book")
        self.rs = ReviewSummary.objects.create(book=self.book)

    def _login_user(self):
        self.client.login(username="user1", password="pass12345")

    @patch("books.views.generate_review_summary_for_book.delay")
    def test_non_moderator_cannot_access(self, mock_delay):
        self._login_user()

        url = reverse("generate_summary", kwargs={"book_id": self.book.id})
        resp = self.client.post(url)

        self.assertIn(resp.status_code, (302, 403))
        mock_delay.assert_not_called()


    def test_user_cannot_delete_others_review(self):
        self.user1_review = Review.objects.create(user=self.user1, book=self.book, rating=5, review_text='ok')

        self.client.login(username="user2", password='pass12345')

        url = reverse("delete_your_review", kwargs={"review_id": self.user1_review.id})
        resp = self.client.post(url)

        self.assertEqual(resp.status_code, 404)

        self.assertTrue(Review.objects.filter(id=self.user1_review.id).exists())

    def test_user_can_delete_his_review(self):
        self.user1_review = Review.objects.create(user=self.user1, book=self.book, rating=5, review_text='ok')

        self.client.login(username="user1", password='pass12345')

        url = reverse("delete_your_review", kwargs={"review_id": self.user1_review.id})
        resp = self.client.post(url)

        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Review.objects.filter(id=self.user1_review.id).exists())


class ReviewSummaryTests(TransactionTestCase):
    def setUp(self):
        self.moderator = User.objects.create_user(username="moderator", password="pass12345", email='mod@email.com')
        self.book = Book.objects.create(title="Test Book")
        self.rs = ReviewSummary.objects.create(book=self.book)

        mod_group, _ = Group.objects.get_or_create(name="Moderator")
        self.moderator.groups.add(mod_group)

    def _login_mod(self):
        self.client.login(username="moderator", password="pass12345")

    
    @patch("books.views.generate_review_summary_for_book.delay")
    def test_moderator_enqueues_task_when_not_generating(self, mock_delay):
        self._login_mod()

        url = reverse("generate_summary", kwargs={"book_id": self.book.id})
        resp = self.client.post(url)

        mock_delay.assert_called_once_with(self.book.id)
        self.assertEqual(resp.status_code, 302)

    @patch("books.views.generate_review_summary_for_book.delay")
    def test_moderator_blocked_when_is_generating_true(self, mock_delay):
        self._login_mod()

        self.rs.is_generating = True
        self.rs.save(update_fields=["is_generating"])

        url = reverse("generate_summary", kwargs={"book_id": self.book.id})
        resp = self.client.post(url)

        mock_delay.assert_not_called()
        self.assertEqual(resp.status_code, 302)
