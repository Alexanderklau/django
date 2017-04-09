# -*- coding: utf-8 -*-
from django.conf import settings
from django.shortcuts import render_to_response, get_object_or_404, redirect
from django.template import RequestContext,Template
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from business_manager.order.apply_models import Apply
from business_manager.review.models import Review, ReviewRecord
from business_manager.config_center.models import *
from business_manager.config_center.models import *
from business_manager.util.permission_decorator import page_permission
from business_manager.employee.models import check_employee, get_employee, get_employee_platform

import traceback
import urllib2
import json
import base64
from time import sleep

def http_get(url):
    try:
        print " in http_get "
        print url
        req = urllib2.Request(url = url)
        rsp = urllib2.urlopen(req,timeout=10).read()
        return rsp
    except Exception,e:
        return json.dumps({"msg": "请求超时", "code": -9901})

def http_post(url, data):
    try:
        req = urllib2.Request(url, data = data)
        rsp = urllib2.urlopen(req,timeout=10).read()
        return rsp
    except Exception,e:
        return json.dumps({"msg": "请求超时", "code": -9901})

@csrf_exempt
@page_permission(check_employee)
def get_submitted_profile(request):
    print '-' * 64
    key, product = '', ''
    if request.method == 'POST':
        key = request.POST.get("key")
        product = request.POST.get('product')
    if request.method == 'GET':
        key = request.GET.get("key")
        product = request.POST.get('product')
    if ProfileFlow.objects.filter(is_in_use=1).count() == 0:
        return HttpResponse(json.dumps({'code':-1, 'msg':'没有模板是启用状态。'}))
    platform = get_employee_platform(request)[0].name
    
    url = 'http://{0}:{1}/get_submitted_profile?search_key={2}&product={3}&platform={4}'.format(settings.WEB_HTTP_SERVER['HOST'],
                                                                                               settings.WEB_HTTP_SERVER['PORT'],
                                                                                               key, product, platform)
    rsp = http_get(url)
    # print "rsp is "  + rsp
    try:
        rsp_json = json.loads(rsp)
    except Exception, e:
        return HttpResponse(json.dumps(
            {
                "code": -1,
                "msg": "error" + str(e)
            }
        ))
    if int(rsp_json.get("code", -1)) < 0:
        return HttpResponse(rsp)
    if rsp_json["logic_rsp"]["int32_apply_status"] == 4:
        apply_id = Apply.objects.filter(create_by=rsp_json["logic_rsp"]["int32_user_id"], product = product).order_by('-id')[0].id
        review_id = Review.objects.filter(order_id=apply_id).order_by('-id')[0].id
        review_record = ReviewRecord.objects.filter(review_type__in=["n"], review_id=review_id).order_by('-id').first()
        if review_record:
            message = review_record.review_message
            rsp_json["msg"] = message
        rsp = json.dumps(rsp_json)
    print rsp_json
    res = HttpResponse(json.dumps(rsp_json))
    return res

@page_permission(check_employee)
def get_flow(request):
    if request.method == 'GET':
        product = request.GET.get('product')
        platform = get_employee_platform(request)[0].name
        url = 'http://{0}:{1}/get_flow?platform={2}&product={3}'.format(settings.WEB_HTTP_SERVER['HOST'], settings.WEB_HTTP_SERVER['PORT'],
                                                                       platform, product)
        rsp = http_get(url)
        return HttpResponse(rsp)


@csrf_exempt
@page_permission(check_employee)
def add_user(request):
    if request.method == 'POST':
        id_no = request.POST.get('id_no')
    if request.method == 'GET':
        id_no = request.GET.get('id_no')
    platform = get_employee_platform(request)[0].name
    url = 'http://{0}:{1}/add_user'.format(settings.WEB_HTTP_SERVER['HOST'], settings.WEB_HTTP_SERVER['PORT'])
    data = {'string_id_no': id_no, 'string_password': '123456', 'string_channel': 'lupeng', 'string_platform': platform}
    rsp = http_post(url,json.dumps(data))
    return HttpResponse(rsp)

@csrf_exempt
@page_permission(check_employee)
def upload_img(request):
    try:
        if request.method == 'POST':
            img = request.POST.get('img')
            data = 'bytes=%s&type=png&encoder=urlbase64'%(img)
            url = setting.IMAGE_SERVER_URL + 'bytes'
    
            rsp = http_post(url,data)
    
            return HttpResponse(rsp)
    except Exception,e:
        return HttpResponse('{"msg": "请求超时", "code": -9901}')

@csrf_exempt
@page_permission(check_employee)
def submit_module(request):
    if request.method == 'POST':
        data = request.POST.dict()
        for item in data.items():
            if item[0].startswith('int32'):
                data[item[0]] = int(data[item[0]])
            if item[0] == 'string_contact':
                contacts = item[1].split('|')
                contact_list = list()
                for contact in contacts:
                    attributes = contact.split('_')
                    contact_dict = {}
                    contact_dict['string_name'] = attributes[0]
                    contact_dict['string_relationship'] = attributes[1]
                    contact_dict['string_phone'] = attributes[2]
                    if len(attributes) >= 4:
                        contact_dict['string_address'] = attributes[3]
                    contact_list.append(contact_dict)
                data['contact_list'] = contact_list
                data.pop('string_contact')
        data['uin'] = int(data['uin'])
        url = 'http://{0}:{1}/submit_module_info'.format(settings.WEB_HTTP_SERVER['HOST'], settings.WEB_HTTP_SERVER['PORT'])
        rsp = http_post(url, json.dumps(data))
        print "rsp is " + rsp
        return HttpResponse(rsp)

@csrf_exempt
@page_permission(check_employee)
def submit_phonecall(request):
    if request.method == 'POST':
        data = request.POST.dict()
        uin = int(data['uin'])
        data['uin'] = uin
        module_id = int(data['int32_module_id'])
        data['int32_module_id'] = module_id
        url = 'http://{0}:{1}/submit_mobile_account'.format(settings.WEB_HTTP_SERVER['HOST'], settings.WEB_HTTP_SERVER['PORT'])
        rsp = http_post(url,json.dumps(data))

        r_data = json.loads(rsp)
        if r_data['code'] != 0:
            return HttpResponse(rsp)

        while 1:
            url = 'http://{0}:{1}/get_mobile_status?uin={2}&module_id={3}'.format(settings.WEB_HTTP_SERVER['HOST'], settings.WEB_HTTP_SERVER['PORT'],
                                                                                 uin, module_id)
            rsp = http_get(url)
            r_data = json.loads(rsp)
            if r_data['code'] != 0:
                break
            if r_data['logic_rsp']['int32_retcode'] != -5:
                break;
            sleep(3)
        if r_data['code'] == 0:
            r_data = json.loads(rsp)
            r_data['logic_rsp']['string_errmsg'] = base64.b64decode(r_data['logic_rsp']['string_errmsg'])
            rsp = json.dumps(r_data)
        return HttpResponse(rsp)

@csrf_exempt
@page_permission(check_employee)
def new_apply(request):
    print request
    if request.method == 'POST':
        data = request.POST.dict()
        platform = get_employee_platform(request)[0].name
        url = 'http://{0}:{1}/new_apply'.format(settings.WEB_HTTP_SERVER['HOST'], settings.WEB_HTTP_SERVER['PORT'])
        data['uin'] = int(data['uin'])
        data['string_platform'] = platform
        rsp = http_post(url,json.dumps(data))

        return HttpResponse(rsp)

@csrf_exempt
@page_permission(check_employee)
def submit_commodity_info(request):
    if request.method == 'POST':
        data = request.POST.dict()
        url = 'http://{0}:{1}/submit_commodity_info'.format(settings.WEB_HTTP_SERVER['HOST'], settings.WEB_HTTP_SERVER['PORT'])
        rsp = http_post(url, json.dumps(data))
        return HttpResponse(rsp)

@csrf_exempt
@page_permission(check_employee)
def submit_apply_info(request):
    if request.method == 'POST':
        salesman = get_employee(request)
        data = request.POST.dict()
        print data
        for key in data:
            if key.startswith('int32'):
                data[key] = int(data[key])
        if salesman:
            data['string_salesman_code'] = salesman.user.username
        else:
            print 'cannot find salesman'
            data['string_salesman_code'] = '0'
        url = 'http://{0}:{1}/submit_apply_info'.format(settings.WEB_HTTP_SERVER['HOST'], settings.WEB_HTTP_SERVER['PORT'])
        print url
        print data
        rsp = http_post(url, json.dumps(data))
        return HttpResponse(rsp)

@csrf_exempt
@page_permission(check_employee)
def get_pre_loan_info(request):
    if request.method == 'GET':
        data = request.GET.dict()
        print data
        url = 'http://{0}:{1}/get_pre_loan_info'.format(settings.WEB_HTTP_SERVER['HOST'], settings.WEB_HTTP_SERVER['PORT'])
        rsp = http_post(url, json.dumps(data))
        return HttpResponse(rsp)




