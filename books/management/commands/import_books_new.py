import ast
import csv
import re
from pathlib import Path
from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, connection
from django.db.models import CharField

from books.models import Book, Author, Tag, Publisher


# ---------- helpers ----------

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


_YEAR_RE = re.compile(r"(\d{4})")


def parse_year(value):
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.lower() == "nan":
        return None
    m = _YEAR_RE.search(s)
    if not m:
        return None
    try:
        year = int(m.group(1))
        if 0 < year < 3000:
            return year
    except ValueError:
        return None
    return None


def get_charfield_maxlen(model, field_name: str, default: int = 255) -> int:
    try:
        f = model._meta.get_field(field_name)
        if isinstance(f, CharField) and getattr(f, "max_length", None):
            return int(f.max_length)
    except Exception:
        pass
    return default


def clamp(value, max_len: int):
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    if len(s) > max_len:
        return s[:max_len]
    return s


def chunks(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


# ---------- command ----------

class Command(BaseCommand):
    help = "Import books from CSV using bulk_create (fast; Postgres-friendly)."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str, help="Path to books CSV")
        parser.add_argument("--encoding", type=str, default="utf-8")
        parser.add_argument("--batch-size", type=int, default=2000)
        parser.add_argument("--progress-every", type=int, default=2000)

        parser.add_argument("--reset", action="store_true")
        parser.add_argument("--reset-authors-tags", action="store_true")

    def _postgres_truncate(self, tables):
        qnames = ", ".join(connection.ops.quote_name(t) for t in tables)
        sql = f"TRUNCATE TABLE {qnames} RESTART IDENTITY CASCADE;"
        with connection.cursor() as cur:
            cur.execute(sql)

    def handle(self, *args, **options):
        csv_path = Path(options["csv_path"])
        if not csv_path.exists():
            raise CommandError(f"The file doesn't exist: {csv_path}")

        encoding = options["encoding"]
        batch_size = options["batch_size"]
        progress_every = options["progress_every"]
        do_reset = options["reset"]
        reset_authors_tags = options["reset_authors_tags"]

        vendor = connection.vendor

        # dynamic max_length
        BOOK_TITLE_MAX = get_charfield_maxlen(Book, "title", 150)
        AUTHOR_NAME_MAX = get_charfield_maxlen(Author, "name", 150)
        TAG_NAME_MAX = get_charfield_maxlen(Tag, "name", 150)
        PUBLISHER_NAME_MAX = get_charfield_maxlen(Publisher, "publisher_name", 150)

        if do_reset:
            self.stdout.write(self.style.WARNING("RESET enabled. Wiping data..."))
            with transaction.atomic():
                if vendor == "postgresql":
                    tables = [Book._meta.db_table]
                    if reset_authors_tags:
                        tables.extend([
                            Author._meta.db_table,
                            Tag._meta.db_table,
                            Publisher._meta.db_table,
                        ])
                    self._postgres_truncate(tables)
                else:
                    Book.objects.all().delete()
                    if reset_authors_tags:
                        Author.objects.all().delete()
                        Tag.objects.all().delete()
                        Publisher.objects.all().delete()

        # caches from DB
        existing_books = dict(Book.objects.values_list("title", "id"))
        author_cache = {name.casefold(): a_id for a_id, name in Author.objects.values_list("id", "name") if name}
        tag_cache = {name.casefold(): t_id for t_id, name in Tag.objects.values_list("id", "name") if name}
        publisher_cache = {name.casefold(): p_id for p_id, name in Publisher.objects.values_list("id", "publisher_name") if name}

        # We’ll collect:
        # - pending books data
        # - needed publishers/authors/tags (names)
        # - m2m edges by book_title -> list of names (temporary), then convert to ids later
        pending_books = []
        book_to_authors = defaultdict(list)  # title -> [author_name...]
        book_to_tags = defaultdict(list)     # title -> [tag_name...]
        needed_publishers = set()
        needed_authors = set()
        needed_tags = set()

        rows_processed = 0

        # ---------- read CSV, build in-memory plan ----------
        with csv_path.open("r", encoding=encoding, newline="") as f:
            reader = csv.DictReader(f)
            required = {"Title", "description", "authors", "publishedDate", "infoLink", "categories"}
            missing = required - set(reader.fieldnames or [])
            if missing:
                raise CommandError(f"Missing columns in books CSV: {missing}")

            for row in reader:
                rows_processed += 1

                title = clamp(row.get("Title"), BOOK_TITLE_MAX)
                if not title:
                    continue
                if title in existing_books:
                    continue  # already imported

                description = (row.get("description") or "").strip() or None
                publication_year = parse_year(row.get("publishedDate"))
                info_link = (row.get("infoLink") or "").strip() or None

                publisher_name = clamp(row.get("publisher"), PUBLISHER_NAME_MAX)
                if publisher_name:
                    needed_publishers.add(publisher_name)

                authors_list = [clamp(x, AUTHOR_NAME_MAX) for x in parse_listish(row.get("authors"))]
                authors_list = [x for x in authors_list if x]
                if authors_list:
                    book_to_authors[title].extend(authors_list)
                    needed_authors.update(authors_list)

                tags_list = [clamp(x, TAG_NAME_MAX) for x in parse_listish(row.get("categories"))]
                tags_list = [x for x in tags_list if x]
                if tags_list:
                    book_to_tags[title].extend(tags_list)
                    needed_tags.update(tags_list)

                pending_books.append({
                    "title": title,
                    "description": description,
                    "publication_year": publication_year,
                    "publisher_name": publisher_name,  # temporarily by name
                    "info_link": info_link,
                })

                if rows_processed % progress_every == 0:
                    self.stdout.write(f"Scanned rows: {rows_processed:,} | Pending new books: {len(pending_books):,}")

        if not pending_books:
            self.stdout.write(self.style.SUCCESS("Nothing to import (no new books)."))
            return

        # ---------- execute import in one transaction ----------
        created_books = 0
        created_m2m_authors = 0
        created_m2m_tags = 0

        # Through models for M2M
        BookAuthor = Book.authors.through
        BookTag = Book.tags.through

        with transaction.atomic():
            # 1) Publishers bulk
            new_publishers = []
            for name in needed_publishers:
                k = name.casefold()
                if k not in publisher_cache:
                    new_publishers.append(Publisher(publisher_name=name))

            if new_publishers:
                Publisher.objects.bulk_create(new_publishers, batch_size=batch_size, ignore_conflicts=True)
                # refresh cache for created/known
                publisher_cache = {name.casefold(): p_id for p_id, name in Publisher.objects.values_list("id", "publisher_name") if name}

            # 2) Authors bulk
            new_authors = []
            for name in needed_authors:
                k = name.casefold()
                if k not in author_cache:
                    new_authors.append(Author(name=name))

            if new_authors:
                Author.objects.bulk_create(new_authors, batch_size=batch_size, ignore_conflicts=True)
                author_cache = {name.casefold(): a_id for a_id, name in Author.objects.values_list("id", "name") if name}

            # 3) Tags bulk
            new_tags = []
            for name in needed_tags:
                k = name.casefold()
                if k not in tag_cache:
                    new_tags.append(Tag(name=name))

            if new_tags:
                Tag.objects.bulk_create(new_tags, batch_size=batch_size, ignore_conflicts=True)
                tag_cache = {name.casefold(): t_id for t_id, name in Tag.objects.values_list("id", "name") if name}

            # 4) Books bulk
            new_book_objs = []
            for b in pending_books:
                publisher_id = None
                if b["publisher_name"]:
                    publisher_id = publisher_cache.get(b["publisher_name"].casefold())

                new_book_objs.append(
                    Book(
                        title=b["title"],
                        description=b["description"],
                        publication_year=b["publication_year"],
                        publisher_id=publisher_id,
                        info_link=b["info_link"],
                        is_active=True,
                    )
                )

            # If you have a DB UNIQUE constraint on title, ignore_conflicts=True is safe.
            # If you DON'T have unique constraint, ignore_conflicts won't help with duplicates.
            Book.objects.bulk_create(new_book_objs, batch_size=batch_size, ignore_conflicts=True)

            # refresh book ids for titles we just inserted
            # (we query only the titles we intended to insert to keep it lighter)
            inserted_titles = [b["title"] for b in pending_books]
            title_to_id = dict(Book.objects.filter(title__in=inserted_titles).values_list("title", "id"))
            created_books = len(title_to_id)

            # 5) M2M bulk - Authors
            book_author_links = []
            for title, author_names in book_to_authors.items():
                book_id = title_to_id.get(title)
                if not book_id:
                    continue
                # de-dup per book
                seen = set()
                for name in author_names:
                    k = name.casefold()
                    a_id = author_cache.get(k)
                    if not a_id:
                        continue
                    key = (book_id, a_id)
                    if key in seen:
                        continue
                    seen.add(key)
                    book_author_links.append(BookAuthor(book_id=book_id, author_id=a_id))

            if book_author_links:
                BookAuthor.objects.bulk_create(
                    book_author_links,
                    batch_size=batch_size,
                    ignore_conflicts=True,  # requires unique constraint on through-table pairs (Django usually makes it)
                )
                created_m2m_authors = len(book_author_links)

            # 6) M2M bulk - Tags
            book_tag_links = []
            for title, tag_names in book_to_tags.items():
                book_id = title_to_id.get(title)
                if not book_id:
                    continue
                seen = set()
                for name in tag_names:
                    k = name.casefold()
                    t_id = tag_cache.get(k)
                    if not t_id:
                        continue
                    key = (book_id, t_id)
                    if key in seen:
                        continue
                    seen.add(key)
                    book_tag_links.append(BookTag(book_id=book_id, tag_id=t_id))

            if book_tag_links:
                BookTag.objects.bulk_create(
                    book_tag_links,
                    batch_size=batch_size,
                    ignore_conflicts=True,
                )
                created_m2m_tags = len(book_tag_links)

        self.stdout.write(self.style.SUCCESS(
            "Import finished.\n"
            f"- Rows scanned: {rows_processed:,}\n"
            f"- Books created (by titles found after insert): {created_books:,}\n"
            f"- Author links inserted (attempted): {created_m2m_authors:,}\n"
            f"- Tag links inserted (attempted): {created_m2m_tags:,}\n"
        ))