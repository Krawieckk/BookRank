from django.core.management.base import BaseCommand
from django.db.models import OuterRef, Subquery, Count, IntegerField, Value
from django.db.models.functions import Coalesce

from books.models import Book, Review


class Command(BaseCommand):
    help = "Update reviews_count for all books"

    def handle(self, *args, **options):
        self.stdout.write("Updating reviews_count...")

        reviews_count_sq = (
            Review.objects
            .filter(book_id=OuterRef("pk"))
            .values("book_id")
            .annotate(c=Count("*"))
            .values("c")
        )

        Book.objects.update(
            reviews_count=Coalesce(
                Subquery(reviews_count_sq, output_field=IntegerField()),
                Value(0)
            )
        )

        self.stdout.write(self.style.SUCCESS("reviews_count updated successfully."))
