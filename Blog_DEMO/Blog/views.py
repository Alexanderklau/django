from django.shortcuts import render
import logging
from django.conf import settings
from .models import *
from django.core.paginator import Paginator,InvalidPage,EmptyPage,PageNotAnInteger
logger = logging.getLogger('blog.views')

def global_setting(request):
    return {
        'SITE_NAME':settings.SITE_NAME,
        'SITE_DESC':settings.SITE_DESC
    }
def index(request):
    try:
        #分类信息获取
        category_list = Category.objects.all()
        article_list = Article.objects.all()
        paginator = Paginator(article_list,10)
        try:
            page = int(request.GET.get('page',1))
            article_list = paginator.page(page)
        except (EmptyPage,InvalidPage,PageNotAnInteger):
            article_list = paginator.page(1)
    except Exception as e:
        pass
    return render(request,'index.html',locals())
# Create your views here.
