from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.db.models import Q
from .models import Book, Review
from .forms import ReviewForm
from django.shortcuts import redirect, render

# Create your views here.
def home(request):
    user = request.user
    return render(request, 'home.html', context={'user': user})

def book_page(request, pk):
    current_user = request.user
    authenticated = current_user.is_authenticated

    book = get_object_or_404(Book, id=pk)

    if request.method == 'POST':
        review_form = ReviewForm(request.POST)
        if review_form.is_valid():
            review = review_form.save(commit=False)
            review.book = book
            review.user = request.user
            review.save()
            return redirect('book_page', pk=book.pk)
    else:
        review_form = ReviewForm()

    if authenticated:
        current_user_review = Review.objects.filter(book=book, user=request.user).first()
    else:
        current_user_review = None

    if current_user_review is not None:
        reviews = Review.objects.filter(book=book).exclude(id=current_user_review.id)
    else:
        reviews = Review.objects.filter(book=book)

    context = {'book': book, 'reviews': reviews, 'current_user_review': current_user_review, 'review_form': review_form}

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
