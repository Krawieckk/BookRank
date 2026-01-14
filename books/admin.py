from django.contrib import admin
from .models import Author, Tag, Book, Review, ReviewSummary, ReviewHelpfulness, Library 

# Register your models here.
admin.site.register(Author)
admin.site.register(Tag)
admin.site.register(Book)
admin.site.register(Review)
admin.site.register(ReviewSummary)
admin.site.register(ReviewHelpfulness)
admin.site.register(Library)
