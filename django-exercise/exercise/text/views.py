from django.shortcuts import render
from django.contrib.auth.models import User
def hello(requests):
    user_list = User.objects.all()
    return render(requests,'table.html',{'user_list':user_list})
# Create your views here.

