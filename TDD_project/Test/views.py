from django.shortcuts import render
from django.http import HttpResponse
def home_page(request):
    return HttpResponse('<html><title>Hello word!</title></html>')
# Create your views here.
