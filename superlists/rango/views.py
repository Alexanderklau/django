from django.shortcuts import render
from django.http import HttpResponse
def home_page(request):
    return render(request,'home.html')
    #return HttpResponse('<html><title>To-Do lists</title></html>')
# Create your views here.
