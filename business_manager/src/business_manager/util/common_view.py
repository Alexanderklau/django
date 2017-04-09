# -*- coding: utf-8 -*-
from django.conf import settings
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext,Template
from django.http import HttpResponse

from business_manager.util.permission_decorator import page_permission
from business_manager.order.models import *
from business_manager.order import data_views as order_views
from business_manager.review import data_views as review_views


def forbidden_view(request):
    if request.method == 'GET':
        page= render_to_response('common/403.html', {"user" : request.user},
                                 context_instance=RequestContext(request))
        return page

