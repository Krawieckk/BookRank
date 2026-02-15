from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import Avg, OuterRef, Subquery, DecimalField, Value, Q
from django.db.models.functions import Coalesce, Cast

from books.models import Book, Review


class Command(BaseCommand):
    help = "Update average_rating for all books based on reviews"

    def handle(self, *args, **options):
        self.stdout.write("Updating average_ratings...")

        review_filter = Q(book_id=OuterRef("pk"))

        avg_sq = (
            Review.objects
            .filter(review_filter)
            .values("book_id")
            .annotate(a=Avg("rating"))
            .values("a")
        )
        avg_subquery = Cast(
            Subquery(avg_sq),
            output_field=DecimalField(max_digits=3, decimal_places=2),
        )

        Book.objects.update(
            average_rating=Coalesce(
                avg_subquery,
                Value(Decimal("0.00"), output_field=DecimalField(max_digits=3, decimal_places=2)),
            )
        )

        self.stdout.write(self.style.SUCCESS("average_rating updated successfully."))
