from django.shortcuts import render
from django.http import HttpResponse

def index(request):
    context_dict = {'boldmessage':'w am bold thisa is not good!'}

    return render(request,'rango/index.html',context_dict)




# Create your views here.
