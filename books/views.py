from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.db.models import Q
from .models import Book, Review, ReviewHelpfulness
from .forms import ReviewForm, HelpfulReviewForm
from django.shortcuts import redirect, render
from django.contrib import messages
from django.db.models import Exists, OuterRef

# Create your views here.
def home(request):
    user = request.user
    return render(request, 'home.html', context={'user': user})

def book_page(request, pk):
    current_user = request.user
    authenticated = current_user.is_authenticated

    book = get_object_or_404(Book, id=pk)

    review_form = ReviewForm()
    helpful_review_form = HelpfulReviewForm()

    if request.method == 'POST':
        if 'add_review' in request.POST:
            review_form = ReviewForm(request.POST)
            if review_form.is_valid():
                review = review_form.save(commit=False)
                review.book = book
                review.user = request.user
                review.save()
                return redirect('book_page', pk=book.pk)
            
        elif 'mark_helpful' in request.POST:
            helpful_review_form = HelpfulReviewForm(request.POST)
            review_pk = request.POST.get('mark_helpful')
            post_review = Review.objects.get(id=int(review_pk))
            
            helpful_review = helpful_review_form.save(commit=False)
            helpful_review.user = request.user
            helpful_review.review = post_review

            post_review.helpful_count += 1

            helpful_review.save()
            post_review.save()

            return redirect('book_page', pk=book.pk)
            
        elif 'unmark_helpful' in request.POST:
            review_pk = request.POST.get('unmark_helpful')
            post_review = Review.objects.get(id=int(review_pk))

            ReviewHelpfulness.objects.get(user=request.user, review=post_review).delete()

            post_review.helpful_count -= 1
            post_review.save()

            return redirect('book_page', pk=book.pk)


    if authenticated:
        current_user_review = Review.objects.filter(book=book, user=request.user).first()
    else:
        current_user_review = None

    if current_user_review is not None:
        reviews = Review.objects.filter(book=book).exclude(id=current_user_review.id)
    else:
        reviews = Review.objects.filter(book=book)

    reviews = reviews.annotate(
        user_has_liked=Exists(
            ReviewHelpfulness.objects.filter(
                user=request.user,
                review_id=OuterRef('pk')
            )
        )
    )

    context = {'book': book, 
               'reviews': reviews, 
               'current_user_review': current_user_review, 
               'review_form': review_form, 
               'helpful_review_form': helpful_review_form}

    return render(request, 'book_page.html', context)

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
