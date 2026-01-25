from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.db.models import Q
from .models import Book, Review, ReviewHelpfulness, Library, ReviewSummary, Author, Tag
from .forms import ReviewForm
from django.shortcuts import redirect, render
from django.contrib import messages
from django.db.models import Exists, OuterRef, F
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from .tasks import generate_review_summary_for_book
from django.db import transaction
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.http import HttpResponse

# Create your views here.
def home(request):
    popular_authors = ["Louis L'Amour", "Agatha Christie", "William Shakespeare", "Edgar Rice Burroughs", "Rudyard Kipling", "John Buchan", "Zane Grey"]
    popular_tags = ["Fiction", "History", "Religion", "Juvenile Fiction", "Biography & Autobiography", "Business & Economics", "Computers", "Social Science", "Juvenile Nonfiction", "Science", "Education"]

    user = request.user
    return render(request, 'home.html', context={'user': user, 
                                                 'authors': popular_authors, 
                                                 'tags': popular_tags})

def book_page(request, pk):
    book = get_object_or_404(Book, id=pk)

    review_form = ReviewForm()

    if request.user.is_authenticated:
        current_user_review = Review.objects.filter(book=book, user=request.user).first()
        added_to_library = Library.objects.filter(book=book, user=request.user).exists()
    else:
        current_user_review = None
        added_to_library = None

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
        ).order_by('-helpful_count', '-inserted_at')
    else:
        reviews_qs = reviews_qs.annotate(
            user_has_liked=Exists(ReviewHelpfulness.objects.none())
        ).order_by('-helpful_count', '-inserted_at')

    # Top 5 most helpful reviews
    reviews_qs = reviews_qs[:5]

    context = {
        "book": book,
        "reviews": reviews_qs,
        "current_user_review": current_user_review,
        "review_form": review_form,
        "added_to_library": added_to_library
    }
    return render(request, "book_page.html", context)

def all_reviews(request, book_id):
    book = get_object_or_404(Book, pk=book_id)

    if request.user.is_authenticated:
        current_user_review = Review.objects.filter(book=book, user=request.user).first()
    else:
        current_user_review = None

    reviews = Review.objects.filter(book=book).order_by('-helpful_count', '-inserted_at')

    paginator = Paginator(reviews, 5)

    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        'book': book, 
        'reviews': reviews, 
        'current_user_review': current_user_review, 
        'page_obj': page_obj
    }

    return render(request, 'all_reviews.html', context)

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

    if Review.objects.filter(book=book, user=request.user).exists():
        form = ReviewForm(request.POST)
        form.add_error(None, "You already added a review for this book.")
        return render(request, "partials/add_review_response.html", {
            "book": book,
            "review_form": form,
            "current_user_review": Review.objects.filter(book=book, user=request.user).first(),
        }, status=400)

    form = ReviewForm(request.POST)
    if not form.is_valid():
        return render(request, "partials/add_review_response.html", {
            "book": book,
            "review_form": form,
            "current_user_review": None,
        }, status=400)

    review = form.save(commit=False)
    review.book = book
    review.user = request.user
    review.save()

    clean_form = ReviewForm()

    return render(request, "partials/add_review_response.html", {
        "book": book,
        "review_form": clean_form,
        "current_user_review": review
    })

@require_POST
@login_required
def delete_your_review(request, review_id):
    review = get_object_or_404(Review, id=review_id, user=request.user)
    review.delete()

    response = HttpResponse("")
    response['HX-Trigger'] = 'reviewDeleted'

    return response

@login_required
def refresh_review_form(request, book_id):

    book = get_object_or_404(Book, id=book_id)

    return render(request, 'partials/review_form.html', {
        'review_form': ReviewForm(),
        'book': book, 
        "current_user_review": None
    })

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

@require_POST
@login_required
def add_to_read(request, book_id):
    book = get_object_or_404(Book, id=book_id)

    _, created = Library.objects.get_or_create(user=request.user, book=book)
    
    return render(request, 'partials/to_read_button.html', {'added_to_library': True, 'book': book})

@require_POST
@login_required
def remove_to_read(request, book_id):
    book = get_object_or_404(Book, id=book_id)

    deleted, _ = Library.objects.filter(user=request.user, book=book).delete()

    return render(request, 'partials/to_read_button.html', {'added_to_library': False, 'book': book})

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

@staff_member_required
def test_generate_summary_once(request, book_id):
    book = get_object_or_404(Book, pk=book_id)

    with transaction.atomic():
        rs, _ = ReviewSummary.objects.select_for_update().get_or_create(book=book)

        if rs.is_generating or rs.summary_text:
            return redirect("home")

        rs.is_generating = True
        rs.save(update_fields=["is_generating"])

        generate_review_summary_for_book.delay(book.id)

    return redirect("home")

@login_required
def profile(request):
    user = request.user
    return render(request, 'profile.html', {'user': user})

def _get_user_library(user, active_filter):
    entries = Library.objects.filter(user=user)
    if active_filter == "to_read":
        entries = entries.filter(reading_status="to_read")
    elif active_filter == "in_progress":
        entries = entries.filter(reading_status="in_progress")
    elif active_filter == "finished":
        entries = entries.filter(reading_status="finished")

    return entries

@login_required
def library(request):

    active_filter = request.GET.get('filter', 'all')
    user_library = _get_user_library(request.user, active_filter)

    context = {
        'active_filter': active_filter,
        'user_library': user_library
    }

    if request.headers.get('HX-Request'):
       return render(request, "partials/library_content.html", context)

    return render(request, "library.html", context)

@login_required
def update_library_status(request, entry_id, new_status):
    if request.method == 'POST':
        entry = get_object_or_404(Library, id=entry_id, user=request.user)
        entry.reading_status = new_status
        entry.save()

        active_filter = request.GET.get('filter', 'all')
        user_library = _get_user_library(request.user, active_filter)

        context = {
            'active_filter': active_filter, 
            'user_library': user_library
        }
        
        return render(request, 'partials/library_content.html', context)
    
@login_required
def delete_from_library(request, entry_id):
    if request.method == 'POST':
        entry = get_object_or_404(Library, id=entry_id, user=request.user)
        entry.delete()

        active_filter = request.GET.get('filter', 'all')
        user_library = _get_user_library(request.user, active_filter)

        context = {
            'active_filter': active_filter, 
            'user_library': user_library
        }
        
        return render(request, 'partials/library_content.html', context)