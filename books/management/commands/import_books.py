import ast
import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from books.models import Book, Author, Tag


def normalize_title(s: str) -> str:
    return (s or "").strip().casefold()

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

def parse_int(value):
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.lower() == "nan":
        return None
    try:
        return int(float(s))
    except Exception:
        return None


class Command(BaseCommand):
    help = "Import/Update books from CSV (incremental, safe to rerun)."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str, help="Path to books CSV")
        parser.add_argument("--encoding", type=str, default="utf-8")
        parser.add_argument("--progress-every", type=int, default=5000)

    def handle(self, *args, **options):
        csv_path = Path(options["csv_path"])
        if not csv_path.exists():
            raise CommandError(f"The file doesn't exist: {csv_path}")

        encoding = options["encoding"]
        progress_every = options["progress_every"]

        existing_books = {}
        for b_id, b_title in Book.objects.values_list("id", "title"):
            key = normalize_title(b_title)
            if key:
                existing_books[key] = b_id

        author_cache = {name.casefold(): a_id for a_id, name in Author.objects.values_list("id", "name")}
        tag_cache = {name.casefold(): t_id for t_id, name in Tag.objects.values_list("id", "name")}

        created_books = 0
        rows_processed = 0

        m2m_done = set() 

        with csv_path.open("r", encoding=encoding, newline="") as f:
            reader = csv.DictReader(f)
            required = {"Title"}
            missing = required - set(reader.fieldnames or [])
            if missing:
                raise CommandError(f"Missing columns in books CSV: {missing}")

            for row in reader:
                rows_processed += 1

                title = (row.get("Title") or "").strip()
                if not title:
                    continue
                key = normalize_title(title)

                description = (row.get("description") or "").strip() or None
                publication_year = parse_int(row.get("publishedDate"))
                publisher = (row.get("publisher") or "").strip() or None
                cover_image = (row.get("image") or "").strip() or None
                info_link = (row.get("infoLink") or "").strip() or None

                authors_list = parse_listish(row.get("authors"))
                categories_list = parse_listish(row.get("categories"))

                book_id = existing_books.get(key)

                if book_id is None:
                    with transaction.atomic():
                        book = Book.objects.create(
                            title=title,
                            description=description,
                            publication_year=publication_year,
                            publisher=publisher,
                            cover_image=cover_image,
                            info_link=info_link,
                            is_active=True,
                        )
                    existing_books[key] = book.id
                    created_books += 1

                    if book.id not in m2m_done:
                        # Authors
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

                        m2m_done.add(book.id)

                if rows_processed % progress_every == 0:
                    self.stdout.write(
                        f"Processed: {rows_processed:,} | Books created: {created_books:,}"
                    )

        self.stdout.write(self.style.SUCCESS(
            "Books import finished.\n"
            f"- Rows processed: {rows_processed:,}\n"
            f"- Books created: {created_books:,}\n"
        ))
