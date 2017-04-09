#!/usr/bin/env python
# coding=utf-8

from django.conf import settings
from django.shortcuts import render_to_response, get_object_or_404, redirect
from django.template import RequestContext,Template
from django.http import HttpResponse
from django.db.models import Count
from django.views.decorators.csrf import csrf_exempt

from business_manager.new_order import data_views as order_views
from business_manager.util.permission_decorator import page_permission
from business_manager.employee.models import check_employee, get_employee
from business_manager.order.models import *
from business_manager.order.apply_models import *
from business_manager.python_common.log_client import CommonLog as Log
from business_manager.review import user_center_client
from business_manager.util.permission_decorator import page_permission
import traceback
import datetime
import json

@csrf_exempt
@page_permission(check_employee)
def get_home_view(request):
    if request.method == 'GET':
        return render_to_response('neworder/query.html', {}, context_instance=RequestContext(request))

@csrf_exempt
def get_dashboard_data(request):
    if request.method == 'GET':
        try:
            Log().info('get_dashboard_data')
            stime = request.GET.get('stime')
            etime = request.GET.get('etime')
            print stime, etime
            query_time = Q(create_at__lt = etime, create_at__gt = stime)
            query_type = request.GET.get('query_type')
            if query_type == 'by_time':
                result = {'categories': [], 'data': []}
                apply_count_list = Apply.objects.filter(query_time).extra({'date_created': 'date(create_at)'}).values('date_created').annotate(created_count=Count('id'))
                print apply_count_list
                count_dict = {}
                for apply_count in apply_count_list:
                    count_dict[apply_count['date_created'].strftime('%Y-%m-%d')] = apply_count['created_count']
                start_date = datetime.datetime.strptime(stime, "%Y-%m-%d %H:%M:%S")
                end_date = datetime.datetime.strptime(etime, "%Y-%m-%d %H:%M:%S")
                while start_date <= end_date:
                    str_date = start_date.strftime('%Y-%m-%d')
                    result['categories'].append(str_date)
                    if str_date in count_dict:
                        result['data'].append(count_dict[str_date])
                    else:
                        result['data'].append(0)
                    start_date += datetime.timedelta(1)
                return HttpResponse(json.dumps(result))
            else:   #by_area
                result_dict = {}
                apply_list = Apply.objects.filter(query_time)
                for apply in apply_list:
                    user_profile = user_center_client.get_detail_profile(apply.create_by.id)
                    if user_profile and user_profile.detail_profile:
                        detail_profile = json.loads(user_profile.detail_profile)
                        if 'string_family_address' in detail_profile:
                            address = detail_profile['string_family_address'].split('#')
                            address = ''.join(address[:3])
                            if address not in result_dict:
                                result_dict[address] = 1
                            else:
                                result_dict[address] += 1
                result = []
                for item in result_dict.items():
                    result.append({'name': item[0], 'y': item[1]})
                return HttpResponse(json.dumps(result))
        except Exception,e:
            print e


@page_permission(check_employee)
def new_apply_view(request):
    if request.method == 'GET':
        Log().info('new_apply_view')
        return render_to_response('neworder/new_order.html', {}, context_instance=RequestContext(request))


@page_permission(check_employee)
def get_all_apply_view(request):
    if request.method == 'GET':
        columns = order_views.get_order_columns()
        page = render_to_response('neworder/home.html', {"columns" : columns, "datatable" : [], "user" : request.user},
                                context_instance=RequestContext(request))
        return page
