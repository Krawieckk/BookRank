from django.shortcuts import render, redirect
from .forms import RegisterForm, LoginForm
from django.contrib.auth import authenticate, login, logout
from .models import Profile

# Create your views here.
def register_site(request):
    # Todo: If a user is authenticated, refuse to access register and login site
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = RegisterForm(request.POST)

        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password1']

            form.save()
            
            user = authenticate(request, username=username, password=password)

            Profile.objects.create(user=user)
            
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

def logout_site(request):
    logout(request)
    return redirect('home')