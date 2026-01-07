import os
from celery import shared_task
from django.db import transaction
from django.db.models import Count
from openai import OpenAI

from .models import Book, Review, ReviewSummary

def _build_input(reviews):
    parts = []
    for r in reviews:
        txt = (r.review_text or "").strip()
        if not txt:
            continue
        if len(txt) > 1000:
            txt = txt[:1000] + "…"
        parts.append(f"- Ocena: {r.rating}/5\n  Recenzja: {txt}")
    return "\n\n".join(parts)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def generate_review_summary_for_book(self, book_id: int):
    with transaction.atomic():
        book = Book.objects.select_for_update().get(pk=book_id)
        rs, _ = ReviewSummary.objects.select_for_update().get_or_create(book=book)

        if (not book.allow_summary) or (not book.is_active):
            rs.is_generating = False
            rs.save(update_fields=["is_generating"])
            return

        if not rs.is_generating:
            return

    reviews = list(
        Review.objects
        .filter(book_id=book_id, is_active=True, only_rating=False)
        .annotate(helpfulness=Count("reviewhelpfulness"))
        .order_by("-helpfulness", "-inserted_at")[:30]
    )

    input_text = _build_input(reviews)

    if not input_text:
        with transaction.atomic():
            ReviewSummary.objects.filter(book_id=book_id).update(is_generating=False)
        return

    try:
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

        resp = client.responses.create(
            model="gpt-5",
            reasoning={"effort": "low"},
            instructions=(
                "Podsumuj opinie o książce po angielsku (około 500 znaków), bez spoilerów. "
                "Uwzględnij główne plusy/minusy i ogólny odbiór. Nie cytuj dosłownie."
            ),
            input=f"Tytuł: {Book.objects.get(pk=book_id).title}\n\nRecenzje:\n{input_text}",
        )

        summary_text = (resp.output_text or "").strip()

    except Exception as e:
        with transaction.atomic():
            ReviewSummary.objects.filter(book_id=book_id).update(is_generating=False)
        raise self.retry(exc=e)

    with transaction.atomic():
        rs = ReviewSummary.objects.select_for_update().get(book_id=book_id)
        rs.summary_text = (summary_text if summary_text else None)
        rs.last_summarized_count = rs.reviews_added_count
        rs.is_generating = False
        rs.save(update_fields=["summary_text", "last_summarized_count", "is_generating"])

        Book.objects.filter(pk=book_id).update(summary_generated=True)