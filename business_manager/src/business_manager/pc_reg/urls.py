# -*- coding: utf-8 -*-
#from django.conf.urls.defaults import *
from django.conf.urls import patterns, include, url
from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required
from django.views.generic import RedirectView

from business_manager.pc_reg.general_views import *

urlpatterns = patterns('business_manager.pc_reg',
   ## page view
   #(r'^$', RedirectView.as_view(url='/order/all')),
   (r'^search$', login_required(get_submitted_profile)),
   (r'^get_flow$', login_required(get_flow)),
   (r'^add_user$', login_required(add_user)),
   (r'^submit_module$', login_required(submit_module)),
   (r'^submit_phonecall$', login_required(submit_phonecall)),
   (r'^new_apply$', login_required(new_apply)),
   (r'^upload$', login_required(upload_img)),
   (r'^submit_apply_info$', login_required(submit_apply_info)),
   (r'^get_pre_loan_info', login_required(get_pre_loan_info)),

)
