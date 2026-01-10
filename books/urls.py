from django.urls import path, include
from .views import home, book_search_suggestions, book_page, mark_helpful, unmark_helpful, add_review, add_to_read, remove_to_read, test_generate_summary_once, all_reviews

urlpatterns = [
    path('', home, name='home'), 
    path('explore/<int:pk>/', book_page, name='book_page'),
    path('explore/<int:book_id>/reviews/', all_reviews, name='all_reviews'),
    path("book/<int:pk>/review/add/", add_review, name="add_review"),
    path("review/<int:review_id>/helpful/add/", mark_helpful, name="mark_helpful"),
    path("review/<int:review_id>/helpful/remove/", unmark_helpful, name="unmark_helpful"),
    path("book/<int:book_id>/to_read/add/", add_to_read, name='add_to_read'),
    path("book/<int:book_id>/to_read/remove/", remove_to_read, name='remove_to_read'),
    path("search/suggest/", book_search_suggestions, name="book_search_suggestions"),
    path("test-generate-summary/<int:book_id>/", test_generate_summary_once),
]
