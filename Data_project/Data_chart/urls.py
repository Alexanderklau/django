# -*-coding:utf-8 -*- 
__author__ = 'Yemilice_lau'
from django.conf.urls import patterns,url
from Data_chart.views import index
urlpatterns = [
    url(r'^$', index),
    # url(r'^about/$', about, name='about'),
    # url(r'^category/(?P<category_name_slug>[\w\-]+)/$', category, name='category'),
]










# if __name__ == '__main__':