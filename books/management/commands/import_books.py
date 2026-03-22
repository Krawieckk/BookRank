import ast
import csv
from pathlib import Path
from collections import defaultdict
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, connection

from books.models import Book, Author, Tag, Publisher


def parse_list(value):
    if not value:
        return []

    text = str(value).strip()
    if not text or text.lower() == "nan":
        return []

    try:
        parsed = ast.literal_eval(text)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    except Exception:
        pass

    return [text]


def parse_year(value):
    if not value:
        return None

    if 1000 < int(value) < datetime.now().year + 1:
        return value
    return None


def cut_text(value, max_len):
    if not value:
        return None

    text = str(value).strip()
    if not text:
        return None

    return text[:max_len]


class Command(BaseCommand):
    help = "Import książek z pliku CSV do bazy danych."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str, help="Ścieżka do pliku CSV z książkami")
        parser.add_argument("--reset", action="store_true", help="Usuwa książki przed importem")
        parser.add_argument(
            "--reset-authors-tags",
            action="store_true",
            help="Usuwa także autorów, tagi i wydawców"
        )

    def truncate_postgres_tables(self, tables):
        quoted_tables = ", ".join(connection.ops.quote_name(table) for table in tables)
        sql = f"TRUNCATE TABLE {quoted_tables} RESTART IDENTITY CASCADE;"
        with connection.cursor() as cursor:
            cursor.execute(sql)

    def handle(self, *args, **options):
        csv_path = Path(options["csv_path"])

        if not csv_path.exists():
            raise CommandError(f"Plik nie istnieje: {csv_path}")

        encoding = "utf-8"
        batch_size = 2000
        progress_every = 2000

        reset_books = options["reset"]
        reset_related = options["reset_authors_tags"]

        # Limity zgodne z modelami
        TITLE_MAX_LEN = 255
        AUTHOR_MAX_LEN = 200
        TAG_MAX_LEN = 200
        PUBLISHER_MAX_LEN = 150

        if reset_books:
            self.stdout.write(self.style.WARNING("Usuwanie danych przed importem..."))
            with transaction.atomic():
                if connection.vendor == "postgresql":
                    tables = [Book._meta.db_table]

                    if reset_related:
                        tables.extend([
                            Author._meta.db_table,
                            Tag._meta.db_table,
                            Publisher._meta.db_table,
                        ])

                    self.truncate_postgres_tables(tables)
                else:
                    Book.objects.all().delete()

                    if reset_related:
                        Author.objects.all().delete()
                        Tag.objects.all().delete()
                        Publisher.objects.all().delete()

        # Pobranie istniejących rekordów do słowników przyspiesza dalszy import
        existing_books = set(Book.objects.values_list("title", flat=True))
        author_map = {
            name.casefold(): author_id
            for author_id, name in Author.objects.values_list("id", "name")
            if name
        }
        tag_map = {
            name.casefold(): tag_id
            for tag_id, name in Tag.objects.values_list("id", "name")
            if name
        }
        publisher_map = {
            name.casefold(): publisher_id
            for publisher_id, name in Publisher.objects.values_list("id", "publisher_name")
            if name
        }

        books_to_create = []
        book_authors = defaultdict(list)
        book_tags = defaultdict(list)

        publishers_needed = set()
        authors_needed = set()
        tags_needed = set()

        processed_rows = 0

        with csv_path.open("r", encoding=encoding, newline="") as file:
            reader = csv.DictReader(file)

            required_columns = {
                "Title",
                "description",
                "authors",
                "publishedDate",
                "infoLink",
                "categories",
            }
            missing_columns = required_columns - set(reader.fieldnames or [])

            if missing_columns:
                raise CommandError(f"Brak wymaganych kolumn w pliku CSV: {missing_columns}")

            for row in reader:
                processed_rows += 1

                title = cut_text(row.get("Title"), TITLE_MAX_LEN)
                if not title:
                    continue

                if title in existing_books:
                    continue

                description = (row.get("description") or "").strip() or None
                publication_year = parse_year(row.get("publishedDate"))
                info_link = (row.get("infoLink") or "").strip() or None

                publisher_name = cut_text(row.get("publisher"), PUBLISHER_MAX_LEN)
                if publisher_name:
                    publishers_needed.add(publisher_name)

                authors = [cut_text(author, AUTHOR_MAX_LEN) for author in parse_list(row.get("authors"))]
                authors = [author for author in authors if author]
                if authors:
                    book_authors[title].extend(authors)
                    authors_needed.update(authors)

                tags = [cut_text(tag, TAG_MAX_LEN) for tag in parse_list(row.get("categories"))]
                tags = [tag for tag in tags if tag]
                if tags:
                    book_tags[title].extend(tags)
                    tags_needed.update(tags)

                books_to_create.append({
                    "title": title,
                    "description": description,
                    "publication_year": publication_year,
                    "publisher_name": publisher_name,
                    "info_link": info_link,
                })

                if processed_rows % progress_every == 0:
                    self.stdout.write(
                        f"Przetworzono wierszy: {processed_rows:,} | "
                        f"Nowe książki: {len(books_to_create):,}"
                    )

        if not books_to_create:
            self.stdout.write(self.style.SUCCESS("Brak nowych książek do zaimportowania."))
            return

        BookAuthor = Book.authors.through
        BookTag = Book.tags.through

        created_books = 0
        created_author_links = 0
        created_tag_links = 0

        with transaction.atomic():
            # Najpierw tworzeni są wydawcy, autorzy i tagi, żeby potem można było przypisać ich identyfikatory do książek i relacji many-to-many.

            new_publishers = []
            for name in publishers_needed:
                key = name.casefold()
                if key not in publisher_map:
                    new_publishers.append(Publisher(publisher_name=name))

            if new_publishers:
                Publisher.objects.bulk_create(
                    new_publishers,
                    batch_size=batch_size,
                    ignore_conflicts=True
                )
                publisher_map = {
                    name.casefold(): publisher_id
                    for publisher_id, name in Publisher.objects.values_list("id", "publisher_name")
                    if name
                }

            new_authors = []
            for name in authors_needed:
                key = name.casefold()
                if key not in author_map:
                    new_authors.append(Author(name=name))

            if new_authors:
                Author.objects.bulk_create(
                    new_authors,
                    batch_size=batch_size,
                    ignore_conflicts=True
                )
                author_map = {
                    name.casefold(): author_id
                    for author_id, name in Author.objects.values_list("id", "name")
                    if name
                }

            new_tags = []
            for name in tags_needed:
                key = name.casefold()
                if key not in tag_map:
                    new_tags.append(Tag(name=name))

            if new_tags:
                Tag.objects.bulk_create(
                    new_tags,
                    batch_size=batch_size,
                    ignore_conflicts=True
                )
                tag_map = {
                    name.casefold(): tag_id
                    for tag_id, name in Tag.objects.values_list("id", "name")
                    if name
                }

            # Tworzenie książek hurtowo - bulk create
            new_book_objects = []
            for book_data in books_to_create:
                publisher_id = None

                if book_data["publisher_name"]:
                    publisher_id = publisher_map.get(book_data["publisher_name"].casefold())

                new_book_objects.append(
                    Book(
                        title=book_data["title"],
                        description=book_data["description"],
                        publication_year=book_data["publication_year"],
                        publisher_id=publisher_id,
                        info_link=book_data["info_link"],
                        is_active=True,
                    )
                )

            Book.objects.bulk_create(
                new_book_objects,
                batch_size=batch_size,
                ignore_conflicts=True
            )

            inserted_titles = [book["title"] for book in books_to_create]
            title_to_id = dict(
                Book.objects.filter(title__in=inserted_titles).values_list("title", "id")
            )
            created_books = len(title_to_id)

            # Relacje książka-autor
            author_links = []
            for title, authors in book_authors.items():
                book_id = title_to_id.get(title)
                if not book_id:
                    continue

                used_pairs = set()

                for author_name in authors:
                    author_id = author_map.get(author_name.casefold())
                    if not author_id:
                        continue

                    pair = (book_id, author_id)
                    if pair in used_pairs:
                        continue

                    used_pairs.add(pair)
                    author_links.append(BookAuthor(book_id=book_id, author_id=author_id))

            if author_links:
                BookAuthor.objects.bulk_create(
                    author_links,
                    batch_size=batch_size,
                    ignore_conflicts=True
                )
                created_author_links = len(author_links)

            # Relacje książka-tag
            tag_links = []
            for title, tags in book_tags.items():
                book_id = title_to_id.get(title)
                if not book_id:
                    continue

                used_pairs = set()

                for tag_name in tags:
                    tag_id = tag_map.get(tag_name.casefold())
                    if not tag_id:
                        continue

                    pair = (book_id, tag_id)
                    if pair in used_pairs:
                        continue

                    used_pairs.add(pair)
                    tag_links.append(BookTag(book_id=book_id, tag_id=tag_id))

            if tag_links:
                BookTag.objects.bulk_create(
                    tag_links,
                    batch_size=batch_size,
                    ignore_conflicts=True
                )
                created_tag_links = len(tag_links)

        self.stdout.write(self.style.SUCCESS(
            "Import zakończony pomyślnie.\n"
            f"- Przetworzono wierszy: {processed_rows:,}\n"
            f"- Dodane książki: {created_books:,}\n"
            f"- Dodane relacje książka-autor: {created_author_links:,}\n"
            f"- Dodane relacje książka-tag: {created_tag_links:,}"
        ))