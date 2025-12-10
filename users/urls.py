from django.contrib import admin
from django.urls import path
from django.views.generic import TemplateView
from .views import register_site


urlpatterns = [
    # path('register', TemplateView.as_view(template_name='register.html'))
    path('register/', register_site, name='register')
]
