from django.urls import path
from .views import register_site, login_site, logout_site
from django.contrib.auth import views as auth_views
from .forms import AsyncPasswordResetForm

urlpatterns = [
    # path('register', TemplateView.as_view(template_name='register.html'))
    path('register/', register_site, name='register'), 
    path('login/', login_site, name='login'), 
    path('logout/', logout_site, name='logout'), 

    path('password_reset/', auth_views.PasswordResetView.as_view(
            form_class=AsyncPasswordResetForm,
            template_name='password_reset.html', 
            email_template_name='password_reset_email.html', 
            subject_template_name='password_reset_subject.txt'
            ), 
            name='password_reset'
        ),    
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='password_reset_confirm.html'), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='password_reset_complete.html'), name='password_reset_complete'),
]
