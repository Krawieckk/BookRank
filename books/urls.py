from django.urls import path, include
from .views import home, book_search_suggestions, book_page, mark_helpful, unmark_helpful, add_review

urlpatterns = [
    path('', home, name='home'), 
    path('explore/<int:pk>/', book_page, name='book_page'),
    path("book/<int:pk>/review/add/", add_review, name="add_review"),
    path("review/<int:review_id>/helpful/add/", mark_helpful, name="mark_helpful"),
    path("review/<int:review_id>/helpful/remove/", unmark_helpful, name="unmark_helpful"),
    path("search/suggest/", book_search_suggestions, name="book_search_suggestions"),
]
