from django.db import models
from django.contrib.auth import get_user_model
from django.db.models import Q

# Create your models here.
class Author(models.Model):
    name = models.CharField(max_length=200)
    bio = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Tag(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name
    
class Publisher(models.Model):
    publisher_name = models.CharField(max_length=200, unique=True)

    def __str__(self):
        return self.publisher_name
    
class Book(models.Model):
    title = models.CharField(max_length=255)    
    description = models.TextField(blank=True, null=True)
    publication_year = models.IntegerField(blank=True, 
                                           null=True, 
                                           db_index=True)
    average_rating = models.DecimalField(max_digits=3, 
                                         decimal_places=2, 
                                         blank=True, 
                                         null=True, 
                                         db_index=True)
    reviews_count = models.IntegerField(default=0, db_index=True)
    cover_image = models.ImageField(
        upload_to='covers/', 
        blank=True,
        default='default_book.png'
    )
    info_link = models.CharField(max_length=400, blank=True, null=True)
    summary_generated = models.BooleanField(default=False, db_index=True)
    allow_summary = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    authors = models.ManyToManyField(Author, related_name='book_authors', blank=True, null=True)
    tags = models.ManyToManyField(Tag, related_name='book_tags', blank=True, null=True)

    publisher = models.ForeignKey(Publisher, 
                                  related_name='book_publisher', 
                                  blank=True, 
                                  null=True, 
                                  on_delete=models.SET_NULL, 
                                  db_index=True)

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
    inserted_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    helpful_count = models.PositiveIntegerField(default=0, db_index=True)
    is_imported = models.BooleanField(default=False, db_index=True)

    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE)

    class Meta:
        indexes = [
            models.Index(fields=['book', '-helpful_count', '-inserted_at'])
        ]

        constraints = [
            models.UniqueConstraint(
                fields=['book', 'user'], 
                condition=Q(is_imported=False), 
                name='uniq_user_review_except_imported'
            )
        ]

    def __str__(self):
        return f'{self.user} [{self.rating}] -> {self.book}'

class ReviewSummary(models.Model):
    summary_text = models.TextField(blank=True, null=True)
    inserted_at = models.DateTimeField(auto_now_add=True)
    reviews_added_count = models.PositiveIntegerField(default=0)
    last_summarized_count = models.PositiveIntegerField(default=0)
    is_generating = models.BooleanField(default=False)

    book = models.OneToOneField(Book, 
                                on_delete=models.CASCADE, 
                                related_name="review_summary")

    def __str__(self):
        return f'{self.book} summary'

class ReviewHelpfulness(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)

    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    review = models.ForeignKey(Review, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'review'], name='unique_user_review_helpful')
        ]
        indexes = [
            models.Index(fields=['review', 'user'])
        ]

    def __str__(self):
        return f'{self.user} -> {self.review}'

class Library(models.Model):

    reading_status_choices = {
        'to_read': 'to_read', 
        'in_progress': 'in_progress', 
        'finished': 'finished'
    }

    reading_status = models.CharField(default='to_read', 
                                      choices=reading_status_choices)
    
    added_at = models.DateTimeField(auto_now_add=True)
    
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('user', 'book')

    def __str__(self):
        return f'{self.user} -> {self.book}'
    