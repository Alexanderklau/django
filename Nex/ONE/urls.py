# -*-coding:utf-8 -*- 
__author__ = 'Yemilice_lau'
from django.conf.urls import url,include
from django.contrib import admin
from ONE.views import index
urlpatterns = [
    url(r'^', index,name='index'),
]








# if __name__ == '__main__':