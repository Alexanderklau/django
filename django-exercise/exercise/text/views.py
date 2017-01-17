from django.shortcuts import render
from django.contrib.auth.models import User
def hello(requests,a):
    print(a)
    user_list = User.objects.all()
    return render(requests,'table.html',{'user_list':user_list})
# Create your views here.

