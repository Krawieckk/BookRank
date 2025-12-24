from django.urls import path, include
from .views import home, book_search_suggestions

urlpatterns = [
    path('', home, name='home'), 
    path("search/suggest/", book_search_suggestions, name="book_search_suggestions"),
]