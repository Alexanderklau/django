from django.shortcuts import render
from django.http import HttpResponse
from .models import Category,Page

def index(request):
    # context_dict = {'OK': "你问我支持不支持，我是支持的。"}
    category_list = Category.objects.order_by('-name')[:5]
    Context_dicts = {'categoryies':category_list}
    return render(request, 'index.html', Context_dicts)

# Create your views here.
