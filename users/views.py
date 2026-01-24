from django.shortcuts import render, redirect
from .forms import RegisterForm, LoginForm
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .models import Profile
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from .forms import UsernameUpdateForm, CustomPasswordUpdateForm, ProfilePictureChangeForm

# Create your views here.
def register_site(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = RegisterForm(request.POST)

        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password1']

            form.save()
            
            user = authenticate(request, username=username, password=password)
            
            login(request, user)

            return redirect('home')
    else:
        form = RegisterForm()

    return render(request, 'register.html', context={'form': form})


def login_site(request):
    if request.user.is_authenticated:
        return redirect('home')
    error_message = None

    if request.method == 'POST':
        form = LoginForm(request.POST)

        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            
            user = authenticate(request, username=username, password=password)
        
            if user is not None:
                login(request, user)
                return redirect('home')
            else:
                error_message = 'Username or password are wrong. Try again'

    else:
        form = LoginForm()
            
    return render(request, 'login.html', context={'form': form, 'error_message': error_message})

@login_required
def logout_site(request):
    logout(request)
    return redirect('home')

@login_required
def update_password(request, success_message=None):
    form = CustomPasswordUpdateForm(user=request.user)

    if request.method == 'POST':
        form = CustomPasswordUpdateForm(user=request.user, data=request.POST)
        if form.is_valid():
            form.save()
            update_session_auth_hash(request, form.user)
            success_message = 'You have successfully changed your password!'
    return render(request, 'partials/password_change_form.html', {'password_change_form': form, 
                                                                  'success_message': success_message})

@login_required
def update_username(request, new_username=None):
    if request.method == 'POST':
        form = UsernameUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            form = UsernameUpdateForm(instance=request.user)
            new_username = request.user.username
        return render(request, 'partials/username_change_form.html', {'username_change_form': form, 
                                                                      'new_username': new_username})

@login_required
def update_profile_picture(request, success_message=None):
    profile = request.user.profile

    if request.method == 'POST':
        form = ProfilePictureChangeForm(
            data=request.POST, 
            files=request.FILES, 
            instance=profile)
        
        if form.is_valid():
            form.save()
            success_message = 'You have successfully changed your profile picture!'
            form = ProfilePictureChangeForm(instance=profile)
    else:
        form = ProfilePictureChangeForm(instance=profile)

    return render(request, 'partials/profile_picture_change_form.html', {'profile_picture_change_form': form, 
                                                                         'success_message': success_message})

@login_required 
def settings(request):
    return render(request, 'settings.html', {
        'username_change_form': UsernameUpdateForm(instance=request.user), 
        'password_change_form': CustomPasswordUpdateForm(request.user), 
        'profile_picture_change_form': ProfilePictureChangeForm(instance=request.user.profile)
    })