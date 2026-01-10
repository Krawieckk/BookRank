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

@receiver(post_delete, sender=ReviewSummary)
def update_book_after_removing_summary(sender, instance: ReviewSummary, **kwargs):

    book_id = instance.book_id
    
    def update():
        Book.objects.filter(id=book_id).update(
            summary_generated = False
        )

    transaction.on_commit(update)

@receiver(post_save, sender=Review)
def review_created_maybe_trigger_summary(sender, instance: Review, created: bool, **kwargs):
    if not created:
        return

    book = instance.book
    if not book.allow_summary or not book.is_active:
        return

    with transaction.atomic():
        rs, _ = ReviewSummary.objects.select_for_update().get_or_create(book=book)

        # +1 do liczby dodanych recenzji
        ReviewSummary.objects.filter(pk=rs.pk).update(
            reviews_added_count=F("reviews_added_count") + 1
        )
        rs.refresh_from_db()

        should_generate = (
            (not rs.is_generating) and
            (rs.reviews_added_count - rs.last_summarized_count >= 20)
        )

        if not should_generate:
            return

        # ustaw is_generating=True w sposób “atomowy”, żeby uniknąć dubli
        updated = ReviewSummary.objects.filter(pk=rs.pk, is_generating=False).update(is_generating=True)
        if updated != 1:
            return

        def _enqueue():
            from .tasks import generate_review_summary_for_book
            generate_review_summary_for_book.delay(book.id)

        transaction.on_commit(_enqueue)
