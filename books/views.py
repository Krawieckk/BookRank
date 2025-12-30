from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.db.models import Q
from .models import Book, Review

# Create your views here.
def home(request):
    user = request.user
    return render(request, 'home.html', context={'user': user})

def book_page(request, pk):
    current_user = request.user
    authenticated = current_user.is_authenticated

    book = get_object_or_404(Book, id=pk)

    if authenticated:
        current_user_review = Review.objects.filter(book=book, user=request.user).first()

    if current_user_review:
        reviews = Review.objects.filter(book=book).exclude(id=current_user_review.id)
    else:
        reviews = Review.objects.filter(book=book)

    if current_user_review: 
        print('Has review')
    else:
        print('no review')

    context = {'book': book, 'reviews': reviews, 'current_user_review': current_user_review}

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
