from django.urls import path, include
from .views import home, book_search_suggestions, book_page, mark_helpful, unmark_helpful, add_review, add_to_read, remove_to_read, test_generate_summary_once, all_reviews, profile, delete_your_review, refresh_review_form, library, update_library_status, delete_from_library, explore, filter_authors, filter_tags, authors_search_suggestions, tags_search_suggestions, top_rated, delete_summary, delete_and_block_summary, block_summary, allow_summary, change_cover_image, moderator_delete_review

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
    path("test-generate-summary/<int:book_id>/", test_generate_summary_once, name='test_generate_summary_once'),
    path("delete-summary/<int:book_id>/", delete_summary, name='delete_summary'),
    path("delete-and-block-summary/<int:book_id>/", delete_and_block_summary, name='delete_and_block_summary'),
    path("block-summary/<int:book_id>/", block_summary, name='block_summary'),
    path("allow-summary/<int:book_id>/", allow_summary, name='allow_summary'),
    path("change-cover/<int:book_id>/", change_cover_image, name='change_cover_image'),
    path("moderator-delete-review/<int:review_id>/", moderator_delete_review, name='moderator_delete_review'),


    path("profile/", profile, name='profile'), 
    path("library/", library, name='library'),
    path("library/<int:entry_id>/<str:new_status>/", update_library_status, name='update_library_status'),
    path("library/<int:entry_id>/", delete_from_library, name='delete_from_library'),

    path("review/<int:book_id>/refresh_review_form", refresh_review_form, name='refresh_review_form'), 

    path('explore/', explore, name='explore'), 
    # HTMX: wyszukiwarka w sidebarze
    path("explore/filters/authors/", filter_authors, name="filter_authors"),
    path("explore/filters/tags/", filter_tags, name="filter_tags"),

    path('top_rated/', top_rated, name='top_rated')
]
