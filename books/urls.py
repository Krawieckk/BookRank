from django.urls import path
from .views import home, book_search_suggestions, book_page, mark_helpful, unmark_helpful, add_review, add_to_read, remove_to_read, generate_summary, all_reviews, delete_your_review, refresh_review_form, library, update_library_status, delete_from_library, explore, authors_search_suggestions, tags_search_suggestions, top_rated, moderator_delete_summary, moderator_delete_and_block_summary, moderator_block_summary, moderator_allow_summary, moderator_delete_review, best_authors, publishers_search_suggestions

urlpatterns = [
    path('', home, name='home'), 
    path('explore/<int:pk>/', book_page, name='book_page'),
    path('explore/<int:book_id>/reviews/', all_reviews, name='all_reviews'),
    path("book/<int:pk>/review/add/", add_review, name="add_review"),
    path("review/<int:review_id>/helpful/add/", mark_helpful, name="mark_helpful"),
    path("review/<int:review_id>/helpful/remove/", unmark_helpful, name="unmark_helpful"),
    path("review/<int:review_id>/delete_your_review/", delete_your_review, name='delete_your_review'),
    path("book/<int:book_id>/to_read/add/", add_to_read, name='add_to_read'),
    path("book/<int:book_id>/to_read/remove/", remove_to_read, name='remove_to_read'),
    path("search/suggest/", book_search_suggestions, name="book_search_suggestions"),
    path("authors/search/suggest", authors_search_suggestions, name="authors_search_suggestions"),
    path("tags/search/suggest", tags_search_suggestions, name="tags_search_suggestions"),
    path("publishers/search/suggest", publishers_search_suggestions, name="publishers_search_suggestions"),

    path("test-generate-summary/<int:book_id>/", generate_summary, name='generate_summary'),
    path("delete-summary/<int:book_id>/", moderator_delete_summary, name='moderator_delete_summary'),
    path("delete-and-block-summary/<int:book_id>/", moderator_delete_and_block_summary, name='moderator_delete_and_block_summary'),
    path("block-summary/<int:book_id>/", moderator_block_summary, name='moderator_block_summary'),
    path("allow-summary/<int:book_id>/", moderator_allow_summary, name='moderator_allow_summary'),
    path("moderator-delete-review/<int:review_id>/", moderator_delete_review, name='moderator_delete_review'),

    path("library/", library, name='library'),
    path("library/<int:entry_id>/<str:new_status>/", update_library_status, name='update_library_status'),
    path("library/<int:entry_id>/", delete_from_library, name='delete_from_library'),

    path("review/<int:book_id>/refresh_review_form", refresh_review_form, name='refresh_review_form'), 

    path('explore/', explore, name='explore'), 

    path('top-rated/', top_rated, name='top_rated'),
    path('best-authors/', best_authors, name='best_authors'),
]
