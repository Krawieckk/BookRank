from django.urls import path, include
from .views import home, book_search_suggestions, book_page

urlpatterns = [
    path('', home, name='home'), 
    path('explore/<int:pk>/', book_page, name='book_page'),
    path("search/suggest/", book_search_suggestions, name="book_search_suggestions"),
]
