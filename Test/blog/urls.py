# -*-coding:utf-8 -*- 
__author__ = 'Yemilice_lau'
from django.conf.urls import url
from blog.views import archive

urlpatterns = [
    url(r'^$', archive)
]









# if __name__ == '__main__':