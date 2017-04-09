# -*- coding: utf-8 -*-
from django.conf.urls import patterns, url

from rest_framework.routers import DefaultRouter
from business_manager.import_data import views
from django.contrib.auth.decorators import login_required



router = DefaultRouter()
router.register(r'field', views.ImportFieldViewSet)
router.register(r'module', views.ImportModuleViewSet)

urlpatterns = patterns(
    'business_manager.import',
    # url(r'^header/match/', login_required(views.header_match)),
    # url(r'^file/', login_required(views.post_file)),
    # url(r'^progress/', login_required(views.get_import_file_progress)),
    url(r'^header/match/', views.header_match),
    url(r'^file/', views.post_file),
    url(r'^delete/file/', views.delete_file),
    url(r'^progress/', views.get_import_file_progress),
    url(r'^reparse/', views.reparse_file),
) + router.urls
