# -*-coding:utf-8 -*- 
__author__ = 'Yemilice_lau'
from django.conf.urls import url
from rango.views import index

urlpatterns = [
    url(r'^$', index)
]









# if __name__ == '__main__':