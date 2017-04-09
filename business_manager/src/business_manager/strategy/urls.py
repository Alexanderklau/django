# -*- coding: utf-8 -*-
from django.conf.urls import patterns, url

from rest_framework.routers import DefaultRouter
from business_manager.strategy import views



router = DefaultRouter()
# router.register(r'i', views.Strategy2ViewSet)
router.register(r'strategy', views.Strategy2ViewSet)

urlpatterns = patterns(
    "business_manager.strategy",
    url("strategy/repay_calculation/", views.repay_calculation),
) + router.urls
