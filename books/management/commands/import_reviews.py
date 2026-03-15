import csv
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Avg, Count, DecimalField, IntegerField, OuterRef, Q, Subquery, Value
from django.db.models.functions import Cast, Coalesce

from books.models import Book, Review

def normalize_title(title: str) -> str:
    return (title or "").strip().casefold()


def parse_rating(value):
    if value is None:
        return None

    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None

    try:
        rating = int(float(text))
    except ValueError:
        return None

    if 1 <= rating <= 5:
        return rating

    return None

class Command(BaseCommand):
    help = "Import recenzji z pliku CSV i przypisanie ich do książek."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str, help="Ścieżka do pliku CSV z recenzjami")
        parser.add_argument(
            "--reset-system-reviews",
            action="store_true",
            help="Usuwa wcześniej zaimportowane recenzje użytkownika systemowego"
        )

    def handle(self, *args, **options):
        csv_path = Path(options["csv_path"])

        if not csv_path.exists():
            raise CommandError(f"Plik nie istnieje: {csv_path}")

        encoding = "utf-8"
        batch_size = 2000
        progress_every = 50000
        system_username = "system"

        reset_system_reviews = options["reset_system_reviews"]

        User = get_user_model()
        system_user, _ = User.objects.get_or_create(
            username=system_username,
            defaults={
                "email": f"{system_username}@local",
                "is_active": True,
            },
        )

        if reset_system_reviews:
            deleted_count, _ = Review.objects.filter(user=system_user).delete()
            self.stdout.write(
                self.style.WARNING(
                    f"Usunięto {deleted_count:,} obiektów powiązanych z użytkownikiem '{system_username}'."
                )
            )

        # Słownik tytułów książek pozwala szybciej dopasować recenzję do książki
        book_map = {}
        for book_id, title in Book.objects.values_list("id", "title"):
            normalized = normalize_title(title)
            if normalized:
                book_map[normalized] = book_id

        if not book_map:
            raise CommandError("Brak książek w bazie. Najpierw zaimportuj książki.")

        processed_rows = 0
        inserted_reviews = 0
        skipped_book_not_found = 0

        reviews_buffer = []

        with csv_path.open("r", encoding=encoding, newline="") as file:
            reader = csv.DictReader(file)

            required_columns = {"Title", "review/score", "review/text"}
            missing_columns = required_columns - set(reader.fieldnames or [])

            if missing_columns:
                raise CommandError(f"Brak wymaganych kolumn w pliku CSV: {missing_columns}")

            for row in reader:
                processed_rows += 1

                title = (row.get("Title") or "").strip()
                book_id = book_map.get(normalize_title(title))

                if not book_id:
                    skipped_book_not_found += 1
                    continue

                rating = parse_rating(row.get("review/score"))
                if rating is None:
                    continue

                review_text = (row.get("review/text") or "").strip() or None

                reviews_buffer.append(
                    Review(
                        user=system_user,
                        book_id=book_id,
                        rating=rating,
                        review_text=review_text,
                        is_active=True,
                        is_imported=True,
                    )
                )

                inserted_reviews += 1

                if len(reviews_buffer) >= batch_size:
                    with transaction.atomic():
                        Review.objects.bulk_create(reviews_buffer, batch_size=batch_size)
                    reviews_buffer.clear()

                if processed_rows % progress_every == 0:
                    self.stdout.write(
                        f"Przetworzono: {processed_rows:,} | "
                        f"Dodano recenzji: {inserted_reviews:,}"
                    )

            if reviews_buffer:
                with transaction.atomic():
                    Review.objects.bulk_create(reviews_buffer, batch_size=batch_size)
                reviews_buffer.clear()

        self.stdout.write(self.style.SUCCESS(
            "Import recenzji zakończony pomyślnie.\n"
            f"- Przetworzono wierszy: {processed_rows:,}\n"
            f"- Dodano recenzji: {inserted_reviews:,}\n"
            f"- Pominięto (brak książki): {skipped_book_not_found:,}\n"
        ))

        self.stdout.write("Aktualizacja średnich ocen i liczby recenzji książek...")

        review_filter = Q(book_id=OuterRef("pk"))

        avg_rating_sq = (
            Review.objects
            .filter(review_filter)
            .values("book_id")
            .annotate(avg_rating=Avg("rating"))
            .values("avg_rating")
        )

        avg_rating_subquery = Cast(
            Subquery(avg_rating_sq),
            output_field=DecimalField(max_digits=3, decimal_places=2),
        )

        reviews_count_sq = (
            Review.objects
            .filter(book_id=OuterRef("pk"))
            .values("book_id")
            .annotate(total=Count("*"))
            .values("total")
        )

        Book.objects.update(
            average_rating=Coalesce(
                avg_rating_subquery,
                Value(
                    Decimal("0.00"),
                    output_field=DecimalField(max_digits=3, decimal_places=2)
                ),
            ),
            reviews_count=Coalesce(
                Subquery(reviews_count_sq, output_field=IntegerField()),
                Value(0),
            ),
        )

        self.stdout.write(
            self.style.SUCCESS("Dane książek zostały zaktualizowane poprawnie.")
        )