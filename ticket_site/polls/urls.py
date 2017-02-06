# -*-coding:utf-8 -*- 
__author__ = 'Yemilice_lau'

from django.conf.urls import url

from .views import *

urlpatterns = [
    url(r'^$',index,name='index'),
    # ex: /polls/5/
    url(r'^(?P<question_id>[0-9]+)/$', detail, name='detail'),
    # ex: /polls/5/results/
    url(r'^(?P<question_id>[0-9]+)/results/$', results, name='results'),
    # ex: /polls/5/vote/
    url(r'^(?P<question_id>[0-9]+)/vote/$', vote, name='vote'),
]








# if __name__ == '__main__':