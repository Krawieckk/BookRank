from django.shortcuts import render

# Create your views here.
def register_site(request):
    return render(request, 'register.html')