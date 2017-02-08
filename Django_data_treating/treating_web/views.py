from django.shortcuts import render

def index(request):
    context = {
        'title':'data',
        'des':'Just a description',
        'score':'1.0',
    }
    return render(request,'index.html',context)
# Create your views here.
