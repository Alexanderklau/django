from django.shortcuts import render
from django.template import loader,Context
from django.http import HttpResponse
from .models import *


def archive(request):
    posts = BlogPost.objects.all()#ORM关系映射，大量特性
    t = loader.get_template("archive.html")
    c = Context({'post':posts})
    return HttpResponse(t.render(c))
# Create your views here.
