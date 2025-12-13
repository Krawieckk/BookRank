from django.shortcuts import render, redirect

def home(request):
    user = request.user
    return render(request, 'home.html', context={'user': user})