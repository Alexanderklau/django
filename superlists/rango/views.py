from django.shortcuts import render
from django.http import HttpResponse
def home_page(request):
    return render(request,'home.html',{
        'new_item_text':request.POST.get('item_text',''),
    })
    #return HttpResponse('<html><title>To-Do lists</title></html>')
# Create your views here.
