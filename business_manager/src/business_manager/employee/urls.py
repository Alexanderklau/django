#!/usr/bin/env python
# coding=utf-8

from django.conf.urls import patterns, include, url
from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required
from django.views.generic import RedirectView

from business_manager.employee.views import *
from business_manager.employee.captcha import get_captcha

urlpatterns = patterns('business_manager.employee',
                      #(r'^$', get_employee_main_page),
                      # (r'^get_employee_review_list', get_employee_review_list),
                      (r'^get_employee_collection_info', get_employee_collection_info), 
                      (r'^get_employee_review_info', get_employee_review_info), 
                      (r'^get_all_employee_group', login_required(get_all_employee_group)),
                      (r'^new_employee', login_required(new_employee)),
                      (r'^create_employee_group', login_required(create_employee_group)),
                      (r'^add_employee_to_group', login_required(add_employee_to_group)),
                      (r'^remove_employee_from_group', login_required(remove_employee_from_group)),
                      (r'^modify_employee_group', login_required(modify_employee_group)),
                      (r'^delete_employee_group', login_required(delete_employee_group)),
                      (r'^get_employee_group_info', login_required(get_employee_group_info)),
                      (r'^get_employee_group_member', login_required(get_employee_group_member)),
                      (r'^modify_employee/?$', login_required(modify_employee)),
                      (r'^reset_password', login_required(reset_password)),
                      (r'^login', login),
                      (r'^search_employee', login_required(search_employee)),
                      (r'^employee_statistic', login_required(employee_statistic)),
                      (r'^get_employee_info', login_required(get_employee_info)),
                      (r'^change_employee_status', login_required(change_employee_status)),
                      (r'^wx_get_session', wx_get_session),
                      (r'^get_captcha/$', get_captcha),
                      (r'^group/$', get_all_employee_group_info)
                       )
