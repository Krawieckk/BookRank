from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.db.models import Q
from .models import Book, Review, ReviewHelpfulness
from .forms import ReviewForm, HelpfulReviewForm
from django.shortcuts import redirect, render
from django.contrib import messages
from django.db.models import Exists, OuterRef, F
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required

# Create your views here.
def home(request):
    user = request.user
    return render(request, 'home.html', context={'user': user})

def book_page(request, pk):
    book = get_object_or_404(Book, id=pk)

    review_form = ReviewForm()

    if request.user.is_authenticated:
        current_user_review = Review.objects.filter(book=book, user=request.user).first()
    else:
        current_user_review = None

    reviews_qs = Review.objects.filter(book=book)
    if current_user_review:
        reviews_qs = reviews_qs.exclude(id=current_user_review.id)

    if request.user.is_authenticated:
        reviews_qs = reviews_qs.annotate(
            user_has_liked=Exists(
                ReviewHelpfulness.objects.filter(
                    user=request.user,
                    review_id=OuterRef("pk")
                )
            )
        )
    else:
        reviews_qs = reviews_qs.annotate(
            user_has_liked=Exists(ReviewHelpfulness.objects.none())
        )

    context = {
        "book": book,
        "reviews": reviews_qs,
        "current_user_review": current_user_review,
        "review_form": review_form,
    }
    return render(request, "book_page.html", context)

def _user_has_liked_check(qs, user):
    if user.is_authenticated:
        return qs.annotate(
            user_has_liked=Exists(
                ReviewHelpfulness.objects.filter(user=user, review_id=OuterRef('pk'))
            )
        )
    return qs.annotate(user_has_liked=Exists(ReviewHelpfulness.objects.none()))

@require_POST
@login_required
def add_review(request, pk):
    book = get_object_or_404(Book, id=pk)
    form = ReviewForm(request.POST)

    existing_review = Review.objects.filter(book=book, user=request.user).first()
    if existing_review:
        return render(request, 'partials/user_review.html', {'book': book, 'current_user_review': existing_review})

    if not form.is_valid():
        return render(request, 'partials/review_form.html', {"form": form, "book": book})

    review = form.save(commit=False)
    review.book = book
    review.user = request.user
    review.save()
    return render(request, 'partials/user_review.html', {"current_user_review": review})

@require_POST
@login_required
def mark_helpful(request, review_id):
    review = get_object_or_404(Review, id=review_id)

    _, created = ReviewHelpfulness.objects.get_or_create(user=request.user, review=review)
    if created:
        Review.objects.filter(id=review.id).update(helpful_count=F('helpful_count') + 1)
    
    r = _user_has_liked_check(Review.objects.filter(id=review.id), request.user).get()

    return render(request, 'partials/single_review.html', {'review': r})

@require_POST
@login_required
def unmark_helpful(request, review_id):
    review = get_object_or_404(Review, id=review_id)

    deleted, _ = ReviewHelpfulness.objects.filter(user=request.user, review=review).delete()
    if deleted:
        Review.objects.filter(id=review.id).update(helpful_count=F("helpful_count") - 1)

    r = _user_has_liked_check(Review.objects.filter(id=review.id), request.user).get()

    return render(request, 'partials/single_review.html', {'review': r})

def book_search_suggestions(request):
    q = (request.GET.get("q") or "").strip()

    if len(q) < 2:
        return JsonResponse({"results": []})

    books = (
        Book.objects
        .filter(
            Q(title__icontains=q) |
            Q(authors__name__icontains=q)
        )
        .distinct()
        .prefetch_related("authors")
        .only("id", "title")
        .order_by("title")[:5]
    )

    results = []
    for b in books:
        author_names = [a.name for a in b.authors.all()]
        results.append({
            "id": b.id,
            "title": b.title,
            "authors": ", ".join(author_names[:3]) + ("…" if len(author_names) > 3 else ""),
            "url": f"/explore/{b.id}/",
        })

    return JsonResponse({"results": results})
