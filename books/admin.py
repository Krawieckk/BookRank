from django.contrib import admin
from .models import Author, Tag, Book, Review, ReviewSummary, ReviewUpVote, ToRead 

# Register your models here.
admin.site.register(Author)
admin.site.register(Tag)
admin.site.register(Book)
admin.site.register(Review)
admin.site.register(ReviewSummary)
admin.site.register(ReviewUpVote)
admin.site.register(ToRead)
