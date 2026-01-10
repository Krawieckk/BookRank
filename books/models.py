from django.db import models
# from django.contrib.auth.models import User
from django.contrib.auth import get_user_model

# Create your models here.
class Author(models.Model):
    name = models.CharField(max_length=200)
    bio = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)

    def __str__(self):
        return self.name

class Tag(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name
    
class Book(models.Model):
    title = models.CharField(max_length=150)    
    description = models.TextField(blank=True, null=True)
    publication_year = models.IntegerField(blank=True, null=True)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, blank=True, null=True)
    reviews_count = models.IntegerField(default=0)
    cover_image = models.CharField(max_length=255, blank=True, null=True)
    publisher = models.CharField(max_length=200, blank=True, null=True)
    info_link = models.CharField(max_length=300, blank=True, null=True)
    summary_generated = models.BooleanField(default=False)
    allow_summary = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    authors = models.ManyToManyField(Author, related_name='book_authors', blank=True)
    tags = models.ManyToManyField(Tag, related_name='book_tags', blank=True)

    def __str__(self):
        return self.title
    
class Review(models.Model):

    rating_choices = [
        (1, "1"),
        (2, "2"),
        (3, "3"),
        (4, "4"),
        (5, "5")
    ]

    rating = models.PositiveSmallIntegerField(choices=rating_choices)
    review_text = models.TextField()
    only_rating = models.BooleanField(default=False)
    inserted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    helpful_count = models.PositiveIntegerField(default=0, db_index=True)

    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE)

    def __str__(self):
        return f'{self.user} [{self.rating}] -> {self.book}'

class ReviewSummary(models.Model):
    summary_text = models.TextField(blank=True, null=True)
    inserted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)
    reviews_added_count = models.PositiveIntegerField(default=0)
    last_summarized_count = models.PositiveIntegerField(default=0)
    is_generating = models.BooleanField(default=False)

    book = models.OneToOneField(Book, on_delete=models.CASCADE, related_name="review_summary")

    def __str__(self):
        return f'{self.book} summary'

class ReviewHelpfulness(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)

    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    review = models.ForeignKey(Review, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "review"], name="uniq_user_review_helpful")
        ]
        indexes = [
            models.Index(fields=['review']), 
            models.Index(fields=['user'])
        ]

    def __str__(self):
        return f'{self.user} -> {self.review}'

class ToRead(models.Model):
    added_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)
    is_finished = models.BooleanField(default=False)

    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('user', 'book')

    def __str__(self):
        return f'{self.user} -> {self.book}'
    