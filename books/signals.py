from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Avg, F
from django.db import transaction
from .models import Review, Book, ReviewSummary

@receiver([post_save, post_delete], sender=Review)
def update_book_rating(sender, instance, **kwargs):
    """
    Update of average rating of the book after any new or deleted reviews
    """
    book_id = instance.book_id

    def update():
        new_avg = Review.objects.filter(
            book_id=book_id, 
            is_active=True
        ).aggregate(avg_rating=Avg('rating'))

        Book.objects.filter(id=book_id).update(
            average_rating = new_avg['avg_rating'] or 0
        )

    transaction.on_commit(update)

@receiver(post_save, sender=Review)
def increase_review_count(sender, instance, **kwargs):
    """
    Increases review_count of the book by 1 after any new reviews
    """
    book_id = instance.book_id

    def update():
        Book.objects.filter(id=book_id).update(
            reviews_count = F('reviews_count') + 1
        )

    transaction.on_commit(update)

@receiver(post_delete, sender=Review)
def decrease_review_count(sender, instance, **kwargs):
    """
    Decreases review_count of the book by 1 after any deleted reviews
    """
    book_id = instance.book_id

    def update():
        Book.objects.filter(id=book_id).update(
            reviews_count = F('reviews_count') - 1
        )

    transaction.on_commit(update)