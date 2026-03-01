import csv
import time
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db import transaction

from books.models import Book, Review


def normalize_title(s: str) -> str:
    return (s or "").strip().casefold()

def clamp_rating(value):
    if value is None:
        return None
    
    s = str(value).strip()
    if not s or s.lower() == "nan":
        return None

    try:
        rating = int(float(s))
    except ValueError:
        return None
    
    if 1 <= rating <= 5:
        return rating

    return None


class Command(BaseCommand):
    help = "Import reviews from CSV and link them to books by Title (bulk insert)."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str, help="Path to reviews CSV")
        parser.add_argument("--encoding", type=str, default="utf-8")
        parser.add_argument("--system-username", type=str, default="system")
        parser.add_argument("--batch-size", type=int, default=1000)
        parser.add_argument("--progress-every", type=int, default=50000)
        parser.add_argument(
            "--reset-system-reviews",
            action="store_true",
            help="Delete existing reviews for system user before importing (restart-friendly).",
        )

    def handle(self, *args, **options):
        csv_path = Path(options["csv_path"])
        if not csv_path.exists():
            raise CommandError(f"The file doesn't exist: {csv_path}")

        encoding = options["encoding"]
        system_username = options["system_username"]
        batch_size = options["batch_size"]
        progress_every = options["progress_every"]
        reset_system_reviews = options["reset_system_reviews"]

        User = get_user_model()
        system_user, _ = User.objects.get_or_create(
            username=system_username,
            defaults={"email": f"{system_username}@local", "is_active": True},
        )

        if reset_system_reviews:
            deleted, _ = Review.objects.filter(user=system_user).delete()
            self.stdout.write(self.style.WARNING(
                f"Deleted {deleted:,} review-related objects for user '{system_username}'."
            ))

        book_map = {}
        for b_id, b_title in Book.objects.values_list("id", "title"):
            k = normalize_title(b_title)
            if k:
                book_map[k] = b_id

        if not book_map:
            raise CommandError("No books found in DB. Import books first.")

        created_reviews = 0
        skipped_book_not_found = 0
        rows_processed = 0

        buffer = []
        start = time.time()

        with csv_path.open("r", encoding=encoding, newline="") as f:
            reader = csv.DictReader(f)

            required = {"Title", "review/score", "review/text"}
            missing = required - set(reader.fieldnames or [])
            if missing:
                raise CommandError(
                    f"Missing columns in reviews CSV: {missing}\n"
                    "If your reviews CSV truly has only score/text, you must add Title column before import."
                )

            for row in reader:
                rows_processed += 1

                title = (row.get("Title") or "").strip()

                book_id = book_map.get(normalize_title(title))
                if not book_id:
                    skipped_book_not_found += 1
                    continue

                rating = clamp_rating(row.get("review/score"))
                if rating is None:
                    continue

                review_text = (row.get("review/text") or "").strip() or None

                buffer.append(
                    Review(
                        user=system_user,
                        book_id=book_id,
                        rating=rating,
                        review_text=review_text,
                        is_active=True,
                    )
                )
                created_reviews += 1

                if len(buffer) >= batch_size:
                    with transaction.atomic():
                        Review.objects.bulk_create(buffer, batch_size=batch_size)
                    buffer.clear()

                if rows_processed % progress_every == 0:
                    self.stdout.write(
                        f"Processed: {rows_processed:,} | Inserted: {created_reviews:,} | "
                    )

            if buffer:
                with transaction.atomic():
                    Review.objects.bulk_create(buffer, batch_size=batch_size)
                buffer.clear()


        self.stdout.write(self.style.SUCCESS(
            "Reviews import finished.\n"
            f"- Rows processed: {rows_processed:,}\n"
            f"- Reviews inserted: {created_reviews:,}\n"
            f"- Skipped (book not found): {skipped_book_not_found:,}\n"
        ))
