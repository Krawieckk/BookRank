from django.contrib import admin
from django.urls import path
from django.views.generic import TemplateView
from .views import register_site, login_site, logout_site


urlpatterns = [
    # path('register', TemplateView.as_view(template_name='register.html'))
    path('register/', register_site, name='register'), 
    path('login/', login_site, name='login'), 
    path('logout/', logout_site, name='logout')
]
