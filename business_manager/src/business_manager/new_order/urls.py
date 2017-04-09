#!/usr/bin/env python
# coding=utf-8

from django.conf.urls import patterns, include, url
from django.contrib.auth.decorators import login_required
from django.views.generic import RedirectView

from business_manager.new_order.general_views import *
from business_manager.new_order.data_views import *
from business_manager.new_order.views import get_applies, query_location_info, get_collect_status, on_or_off_location, zm_auth, zm_result, zm_srouce, commit_common_accounts

urlpatterns = patterns('business_manager.new_order',
                      (r'^$', RedirectView.as_view(url='/new_order/query')),
                      (r'^query', get_home_view),
                      (r'^get_location_info/$', query_location_info),
                      (r'^orders', get_applies),
                      (r'^collect_status/$', get_collect_status),
                      (r'^on_off/$', on_or_off_location),
                      # (r'(?P<path>zm_auth|zm_result|zm_srouce)', zm_auth),
                      (r'^zm_auth/$', zm_auth),
                      (r'^zm_result/$', zm_result),
                      (r'^zm_srouce/$', zm_srouce),
                      (r'^common_accounts/$', commit_common_accounts),
                      (r'^get_dashboard_data', login_required(get_dashboard_data)),
                      (r'^new_apply', login_required(new_apply_view)),
                      (r'^all_apply_list', login_required(get_all_apply_view)),
                      (r'^all_json', login_required(get_all_apply_datatable)))
