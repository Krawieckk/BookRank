from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import Avg, OuterRef, Subquery, DecimalField, Value, Q, Count, IntegerField
from django.db.models.functions import Coalesce, Cast

from books.models import Book, Review


class Command(BaseCommand):
    help = "Update data for all books - average_rating and reviews_cont"

    def handle(self, *args, **options):
        self.stdout.write("Updating data regarding books...")

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

        reviews_count_sq = (
            Review.objects
            .filter(book_id=OuterRef("pk"))
            .values("book_id")
            .annotate(c=Count("*"))
            .values("c")
        )

        Book.objects.update(
            average_rating=Coalesce(
                avg_subquery,
                Value(Decimal("0.00"), output_field=DecimalField(max_digits=3, decimal_places=2)),
            ), 
            reviews_count=Coalesce(
                Subquery(reviews_count_sq, output_field=IntegerField()),
                Value(0)
            )
        )

        self.stdout.write(self.style.SUCCESS("Data regarding books updated successfully."))
