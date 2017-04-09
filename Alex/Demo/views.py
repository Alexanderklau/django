from django.shortcuts import render
from django.http import HttpResponse
# def index(request):
#     context_dict = {'boldmessage':'i am king!'}
#     return render(request,'index.html',context_dict)

def about(request):  #定义函数
    for i in range(1,100):
        text = {i}
        return render(request,'about.html',text)




# Create your views here.
