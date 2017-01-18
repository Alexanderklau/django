from django.shortcuts import render
from django.contrib.auth.models import User
from django.http import request
def hello(request,a):
    # print(request.GET.get('key'))
    user_list = User.objects.all()
    print(user_list.query)
    return render(request,'table.html',{'user_list':user_list})
# Create your views here.

