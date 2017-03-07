from django.shortcuts import render
from django.http import HttpResponse
from .models import Category,Page

def index(request):
    # context_dict = {'OK': "你问我支持不支持，我是支持的。"}
    category_list = Category.objects.order_by('-name')[:5]
    Context_dicts = {'categoryies':category_list}
    return render(request, 'index.html', Context_dicts)

def category(request,category_name_slug):
    # Create a context dictionary which we can pass to the template rendering engine.
    context_dict = {}
    try:
        category = Category.objects.get(slug=category_name_slug)
        context_dict['category_name'] = category.name
        pages = Page.objects.filter(category=category)
        context_dict['pages'] = pages
        context_dict['category'] = category
    except Category.DoesNotExist:
        pass
    return render(request, 'category.html', context_dict)

# Create your views here.
