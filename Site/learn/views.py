#coding:utf-8
import json
from django.shortcuts import render
from django.http import HttpResponse
def add(request):
    a = request.GET['a']
    b = request.GET['b']
    c = int(a) + int(b)
    return HttpResponse(str(c))
def add2(request,a,b):
    c = int(a) + int(b)
    return HttpResponse(str(c))
def home(request):
    List = [u'哈哈','JSON']
    Dict = {'site':u'啊哈哈','author':'alex'}
    return render(request,'home.html',{
        'List': json.dumps(List),
        'Dict': json.dumps(Dict)
    })
    # string = u"Fuck You!"
    # Tutorlisad = ["Html","css","JQuery","Python"]
    # info_dict = {'site':u'hello','content':u'text'}
    # List = map(string,range(100))
    # return render(request,'home.html',{'string':string,'Tutorlisad':Tutorlisad,'info_dict':info_dict,'List':List})


# Create your views here.
