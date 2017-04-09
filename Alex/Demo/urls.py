# -*-coding:utf-8 -*- 
__author__ = 'Yemilice_lau'
from django.conf.urls import url
from django.contrib import admin
from Demo.views import about
urlpatterns = [
    url(r'^',about,name='about')
]










# if __name__ == '__main__':