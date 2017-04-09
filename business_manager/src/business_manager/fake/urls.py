# -*- coding: utf-8 -*-
#from django.conf.urls.defaults import *
from django.conf.urls import patterns, include, url
from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required
from django.views.generic import RedirectView

from business_manager.fake.views import FakeUser

urlpatterns = patterns('business_manager.fake',
   ## page view
   (r'^user/(?P<method>create|delete)$', FakeUser.as_view()),
)
