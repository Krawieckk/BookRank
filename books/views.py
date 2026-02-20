from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.db.models import Q
from .models import Book, Review, ReviewHelpfulness, Library, ReviewSummary, Author, Tag, Publisher
from .forms import ReviewForm
from django.shortcuts import redirect, render
from django.contrib import messages
from django.db.models import Exists, OuterRef, F, Avg, Count, Sum
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from .tasks import generate_review_summary_for_book
from django.db import transaction
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.urls import reverse
from django.contrib.auth.decorators import user_passes_test
from datetime import datetime
from django.core.cache import cache


def _popular_authors():
    return list(
        Author.objects.annotate(
            average_book_rating=Avg('book_authors__average_rating'),
            total_reviews=Sum('book_authors__reviews_count'),
            books_count=Count('book_authors')
        )
        .filter(total_reviews__gt=5, books_count__gte=3)
        .values('id', 'name')
        .order_by('-books_count', '-average_book_rating', '-total_reviews')[:20]
    )

def _popular_tags():
    return list(
        Tag.objects.annotate(book_count=Count('book_tags'))
        .values('id', 'name')
        .order_by('-book_count')[:20]
    )

def _popular_publishers():
    return list(
        Publisher.objects.annotate(
            book_count=Count('book_publisher')
        )
        .values('id', 'publisher_name')
        .order_by('-book_count')[:20]
    )

def _top_rated():
    return list(
        Book.objects
        .filter(average_rating__gte=4.5, reviews_count__gte=100)
        .values('id')
        .order_by('-reviews_count', '-average_rating')
        [:100]
    )

CACHE_SPECS = {
    "home:popular_authors:v1": (_popular_authors, 60 * 100),
    "home:popular_tags:v1": (_popular_tags, 60 * 100),
    "explore:popular_publishers:v1": (_popular_publishers, 60*100), 
    "home:top_rated:v1": (_top_rated, 60*100)
}

def get_cached_results(key, default=None):
    val = cache.get(key)
    if val is not None:
        return val

    spec = CACHE_SPECS.get(key)
    if not spec:
        return []

    builder, timeout = spec
    val = builder()
    cache.set(key, val, timeout=timeout)
    return val


# Create your views here.
def home(request):
    authors_key = 'home:popular_authors:v1'
    tags_key = 'home:popular_tags:v1'

    popular_authors = get_cached_results(authors_key)
    popular_tags = get_cached_results(tags_key)

    user = request.user
    return render(request, 'books/home.html', context={'user': user, 
                                                 'authors': popular_authors, 
                                                 'tags': popular_tags})

def book_page(request, pk):
    book = get_object_or_404(Book, id=pk)

    review_summary = ReviewSummary.objects.filter(book_id=pk).first()

    if review_summary:
        summary_is_generating = review_summary.is_generating
    else:
        summary_is_generating = None

    review_form = ReviewForm()

    if request.user.groups.filter(name='Moderator').exists():
        moderator = True
    else:
        moderator = False

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
        "added_to_library": added_to_library, 
        "moderator_logged": moderator, 
        "review_summary": review_summary, 
        "summary_is_generating": summary_is_generating
    }
    return render(request, "books/book_page.html", context)

def all_reviews(request, book_id):
    book = get_object_or_404(Book, pk=book_id)
    moderator = is_moderator(request.user)

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
        'page_obj': page_obj, 
        'moderator_logged': moderator
    }

    return render(request, 'books/partials/all_reviews.html', context)

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
        return render(request, "books/partials/add_review_response.html", {
            "book": book,
            "review_form": form,
            "current_user_review": Review.objects.filter(book=book, user=request.user).first(),
        }, status=400)

    form = ReviewForm(request.POST)
    if not form.is_valid():
        return render(request, "books/partials/add_review_response.html", {
            "book": book,
            "review_form": form,
            "current_user_review": None,
        }, status=400)

    review = form.save(commit=False)
    review.book = book
    review.user = request.user
    review.save()

    clean_form = ReviewForm()

    return render(request, "books/partials/add_review_response.html", {
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

    return render(request, 'books/partials/review_form.html', {
        'review_form': ReviewForm(),
        'book': book, 
        "current_user_review": None
    })

@require_POST
@login_required
def mark_helpful(request, review_id):
    review = get_object_or_404(Review, id=review_id)
    moderator = is_moderator(request.user)
    print(moderator)

    _, created = ReviewHelpfulness.objects.get_or_create(user=request.user, review=review)
    if created:
        Review.objects.filter(id=review.id).update(helpful_count=F('helpful_count') + 1)
    
    r = _user_has_liked_check(Review.objects.filter(id=review.id), request.user).get()

    return render(request, 'books/partials/single_review.html', {'review': r, 'moderator_logged': moderator})

@require_POST
@login_required
def unmark_helpful(request, review_id):
    review = get_object_or_404(Review, id=review_id)
    moderator = is_moderator(request.user)

    deleted, _ = ReviewHelpfulness.objects.filter(user=request.user, review=review).delete()
    if deleted:
        Review.objects.filter(id=review.id).update(helpful_count=F("helpful_count") - 1)

    r = _user_has_liked_check(Review.objects.filter(id=review.id), request.user).get()

    return render(request, 'books/partials/single_review.html', {'review': r, 'moderator_logged': moderator})

@require_POST
@login_required
def add_to_read(request, book_id):
    book = get_object_or_404(Book, id=book_id)

    _, created = Library.objects.get_or_create(user=request.user, book=book)
    
    return render(request, 'books/partials/to_read_button.html', {'added_to_library': True, 'book': book})

@require_POST
@login_required
def remove_to_read(request, book_id):
    book = get_object_or_404(Book, id=book_id)

    deleted, _ = Library.objects.filter(user=request.user, book=book).delete()

    return render(request, 'books/partials/to_read_button.html', {'added_to_library': False, 'book': book})

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
       return render(request, "books/partials/library_content.html", context)

    return render(request, "books/library.html", context)

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
        
        return render(request, 'books/partials/library_content.html', context)
    
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
        
        return render(request, 'books/partials/library_content.html', context)

SORT_MAP = {
    "rating_desc": "-average_rating",
    "rating_asc": "average_rating",
    "title_asc": "title",
    "title_desc": "-title",
    "newest": "-publication_year",
    "oldest": "publication_year",
}

def explore(request):
    qs = (
        Book.objects
        .prefetch_related("authors", "tags")
        .filter(is_active=True)
    )

    selected_authors = request.GET.getlist("authors")
    selected_tags = request.GET.getlist("tags")
    selected_publishers = request.GET.getlist("publishers")
    min_published_year = request.GET.get("min_published_year")
    max_published_year = request.GET.get("max_published_year")    
    summary_generated = request.GET.get('summary_generated')

    # filters cache
    authors_key = 'home:popular_authors:v1'
    tags_key = 'home:popular_tags:v1'
    publishers_key = 'explore:popular_publishers:v1'

    popular_authors = get_cached_results(authors_key)
    popular_tags = get_cached_results(tags_key)
    popular_publishers = get_cached_results(publishers_key)

    selected_authors_qs = Author.objects.filter(id__in=selected_authors)
    selected_tags_qs = Tag.objects.filter(id__in=selected_tags)
    selected_publishers_qs = Publisher.objects.filter(id__in=selected_publishers)

    base_authors_qs = Author.objects.filter(id__in=[x['id'] for x in popular_authors])
    authors_qs = (base_authors_qs | selected_authors_qs).distinct()

    base_tags_qs = Tag.objects.filter(id__in=[x['id'] for x in popular_tags])
    tags_qs = (base_tags_qs | selected_tags_qs).distinct()

    base_publishers_qs = Publisher.objects.filter(id__in=[x['id'] for x in popular_publishers])
    publishers_qs = (base_publishers_qs | selected_publishers_qs).distinct().order_by('publisher_name')

    selcted_authors_map = {
        a.id: a.name
        for a in Author.objects.filter(id__in=selected_authors_qs)
    }

    selected_tags_map = {
        t.id: t.name
        for t in Tag.objects.filter(id__in=selected_tags_qs)
    }
    
    selected_publishers_map = {
        p.id: p.publisher_name
        for p in Publisher.objects.filter(id__in=selected_publishers_qs)
    }

    selected_filters_count = len(selected_authors) + len(selected_tags) + len(selected_publishers)

    sort = request.GET.get("sort", "rating_desc")

    if selected_authors:
        qs = qs.filter(authors__id__in=selected_authors).distinct()

    if selected_tags:
        qs = qs.filter(tags__id__in=selected_tags).distinct()

    if selected_publishers:
        qs = qs.filter(publisher_id__in=selected_publishers).distinct()

    if min_published_year:
        qs = qs.filter(Q(publication_year__gte=int(min_published_year)))

    if max_published_year:
        qs = qs.filter(Q(publication_year__lte=int(max_published_year)))

    if summary_generated == 'on':
        qs = qs.filter(summary_generated=True)

    qs = qs.order_by(SORT_MAP.get(sort, "-average_rating"))

    paginator = Paginator(qs, 12)
    page_obj = paginator.get_page(request.GET.get("page"))

    params = request.GET.copy()
    params.pop("page", None)
    querystring = params.urlencode()

    context = {
        "page_obj": page_obj,
        "sort": sort,
        "selected_authors": selected_authors,
        "selected_authors_map": selcted_authors_map, 
        "selected_tags": selected_tags,
        "selected_tags_map": selected_tags_map,
        "selected_publishers": selected_publishers, 
        "selected_publishers_map": selected_publishers_map, 
        "authors": authors_qs,
        "tags": tags_qs,
        "publishers": publishers_qs,
        "selected_filters_count": selected_filters_count, 
        "min_published_year": min_published_year, 
        "max_published_year": max_published_year, 
        "summary_generated_filter": summary_generated, 
        "current_year": datetime.now().year, 
        "querystring": querystring
    }

    if request.headers.get("HX-Request") == "true":
        target = request.headers.get('HX-Target')
        if target == 'exploreMain':
            return render(request, "books/partials/explore_main.html", context)
        if target == 'exploreSection':
            return render(request, 'books/partials/explore_section.html', context)

    return render(request, "books/explore.html", context)


def authors_search_suggestions(request):
    q = (request.GET.get("q") or "").strip()

    if len(q) < 2:
        return JsonResponse({"results": []})

    authors = (
        Author.objects
        .filter(
            Q(name__icontains=q)
        )
        .distinct()
        .only("id", "name")
        .order_by("name")[:5]
    )

    base_url = reverse("explore")

    results = []
    for a in authors:
        results.append({
            "id": a.id,
            "name": a.name,
            "url": f"{base_url}?authors={a.id}",
        })

    return JsonResponse({"results": results})

def tags_search_suggestions(request):
    q = (request.GET.get("q") or "").strip()

    if len(q) < 2:
        return JsonResponse({"results": []})

    authors = (
        Tag.objects
        .filter(
            Q(name__icontains=q)
        )
        .distinct()
        .only("id", "name")
        .order_by("name")[:5]
    )

    base_url = reverse("explore")

    results = []
    for a in authors:
        results.append({
            "id": a.id,
            "name": a.name,
            "url": f"{base_url}?tags={a.id}",
        })


    return JsonResponse({"results": results})

def publishers_search_suggestions(request):
    q = (request.GET.get("q") or "").strip()

    if len(q) < 2:
        return JsonResponse({"results": []})

    authors = (
        Publisher.objects
        .filter(
            Q(publisher_name__icontains=q)
        )
        .distinct()
        .only("id", "publisher_name")
        .order_by("publisher_name")[:5]
    )

    base_url = reverse("explore")

    results = []
    for a in authors:
        results.append({
            "id": a.id,
            "publisher_name": a.publisher_name,
            "url": f"{base_url}?publishers={a.id}",
        })


    return JsonResponse({"results": results})

def top_rated(request):
    top_rated_key = 'home:top_rated:v1'
    top_rated_books_list = get_cached_results(top_rated_key)

    qs = Book.objects.filter(id__in=[x['id'] for x in top_rated_books_list])

    paginator = Paginator(qs, 12)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        'page_obj': page_obj
    }

    return render(request, 'books/top_rated.html', context)

def best_authors(request):
    authors_key = 'home:popular_authors:v1'
    popular_authors = get_cached_results(authors_key)

    qs = Book.objects.filter(authors__in=[x['id'] for x in popular_authors])

    paginator = Paginator(qs, 12)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        'page_obj': page_obj
    }

    return render(request, 'books/best_authors.html', context)

def is_moderator(user):
    return user.groups.filter(name='Moderator').exists()

@user_passes_test(is_moderator)
def generate_summary(request, book_id):
    book = get_object_or_404(Book, pk=book_id)

    with transaction.atomic():
        rs, _ = ReviewSummary.objects.select_for_update().get_or_create(book=book)

        if rs.is_generating:
            return redirect("home")

        transaction.on_commit(lambda: generate_review_summary_for_book.delay(book.id))

    return redirect("book_page", pk=book_id)

@user_passes_test(is_moderator)
def moderator_delete_summary(request, book_id):
    o = get_object_or_404(ReviewSummary, book_id=book_id)
    o.delete()

    book = Book.objects.select_for_update().get(id=book_id)
    book.summary_generated = False
    book.save(update_fields=["summary_generated"])

    return redirect('book_page', pk=book_id)

@user_passes_test(is_moderator)
def moderator_delete_and_block_summary(request, book_id):
    o = get_object_or_404(ReviewSummary, book_id=book_id)
    o.delete()

    book = Book.objects.select_for_update().get(id=book_id)
    book.allow_summary = False
    book.summary_generated = False
    book.save(update_fields=["allow_summary", "summary_generated"])

    return redirect('book_page', pk=book_id)

@user_passes_test(is_moderator)
def moderator_block_summary(request, book_id):
    book = Book.objects.select_for_update().get(id=book_id)
    book.allow_summary = False
    book.save(update_fields=['allow_summary'])

    return redirect('book_page', pk=book_id)

def moderator_allow_summary(request, book_id):
    book = Book.objects.select_for_update().get(id=book_id)
    book.allow_summary = True
    book.save(update_fields=['allow_summary'])

    return redirect('book_page', pk=book_id)


@user_passes_test(is_moderator)
def moderator_delete_review(request, review_id):
    with transaction.atomic():
        review = Review.objects.select_for_update().get(id=review_id)
        review.delete()

    return render(request, 'books/partials/all_user_reviews.html')