import ast
import csv
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from books.models import Book, Author, Tag


def parse_listish(value: str):
    if value is None:
        return []
    s = str(value).strip()
    if not s or s.lower() == "nan":
        return []

    try:
        parsed = ast.literal_eval(s)
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if str(x).strip()]
    except Exception:
        pass

    return [s]


class Command(BaseCommand):
    help = "Import books from CSV (incremental, safe to rerun)."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str, help="Path to books CSV")
        parser.add_argument("--encoding", type=str, default="utf-8")
        parser.add_argument("--progress-every", type=int, default=2000)

        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete ALL books (and related objects via CASCADE) before importing.",
        )
        parser.add_argument(
            "--reset-authors-tags",
            action="store_true",
            help="Also delete ALL authors and tags (use with --reset).",
        )

    def handle(self, *args, **options):
        csv_path = Path(options["csv_path"])
        if not csv_path.exists():
            raise CommandError(f"The file doesn't exist: {csv_path}")

        encoding = options["encoding"]
        progress_every = options["progress_every"]
        do_reset = options["reset"]
        reset_authors_tags = options["reset_authors_tags"]

        if do_reset:
            self.stdout.write(self.style.WARNING(
                "RESET enabled: deleting ALL books and related objects "
            ))

            with transaction.atomic():
                deleted_total, deleted_map = Book.objects.all().delete()

                if reset_authors_tags:
                    Author.objects.all().delete()
                    Tag.objects.all().delete()

            self.stdout.write(self.style.WARNING(
                f"Deleted objects (total): {deleted_total:,}"
            ))

        existing_books = {}
        for b_id, b_title in Book.objects.values_list("id", "title"):
            if b_title:
                existing_books[b_title] = b_id

        author_cache = {name.casefold(): a_id for a_id, name in Author.objects.values_list("id", "name")}
        tag_cache = {name.casefold(): t_id for t_id, name in Tag.objects.values_list("id", "name")}

        created_books = 0
        rows_processed = 0

        with csv_path.open("r", encoding=encoding, newline="") as f:
            reader = csv.DictReader(f)

            required = {"Title", "description", "authors", "image", "publishedDate", "infoLink", "categories"}
            missing = required - set(reader.fieldnames or [])
            if missing:
                raise CommandError(f"Missing columns in books CSV: {missing}")

            for row in reader:
                rows_processed += 1

                title = (row.get("Title") or "").strip()
                if not title:
                    continue

                description = (row.get("description") or "").strip() or None
                publication_year = row.get("publishedDate")
                publisher = (row.get("publisher") or "").strip() or None
                cover_image = (row.get("image") or "").strip() or None
                info_link = (row.get("infoLink") or "").strip() or None

                authors_list = parse_listish(row.get("authors"))
                categories_list = parse_listish(row.get("categories"))

                book_id = existing_books.get(title)

                if book_id is None:
                    with transaction.atomic():
                        book = Book.objects.create(
                            title=title,
                            description=description,
                            publication_year=publication_year,
                            cover_image=cover_image,
                            publisher=publisher,
                            info_link=info_link,
                            is_active=True,
                        )
                    existing_books[title] = book.id
                    created_books += 1
                else:
                    continue

                if authors_list:
                    author_ids = []
                    for name in authors_list:
                        k = name.casefold()
                        a_id = author_cache.get(k)
                        if a_id is None:
                            a = Author.objects.create(name=name)
                            a_id = a.id
                            author_cache[k] = a_id
                        author_ids.append(a_id)
                    if author_ids:
                        book.authors.add(*author_ids)

                if categories_list:
                    tag_ids = []
                    for name in categories_list:
                        k = name.casefold()
                        t_id = tag_cache.get(k)
                        if t_id is None:
                            t = Tag.objects.create(name=name)
                            t_id = t.id
                            tag_cache[k] = t_id
                        tag_ids.append(t_id)
                    if tag_ids:
                        book.tags.add(*tag_ids)


                if rows_processed % progress_every == 0:
                    self.stdout.write(
                        f"Processed: {rows_processed:,} | Books created: {created_books:,}"
                    )

        self.stdout.write(self.style.SUCCESS(
            "Books import finished.\n"
            f"- Rows processed: {rows_processed:,}\n"
            f"- Books created: {created_books:,}\n"
        ))
