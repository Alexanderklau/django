# -*- coding: utf-8 -*-
from django.conf import settings
from django.shortcuts import render_to_response, get_object_or_404, redirect
from django.template import RequestContext,Template
from django.http import HttpResponse

from business_manager.util.permission_decorator import page_permission
from business_manager.employee.models import check_employee, get_employee
from business_manager.order.models import *
from business_manager.order import data_views as order_views
from business_manager.review import data_views as review_views
from business_manager.python_common.log_client import CommonLog as Log
from business_manager.review import risk_client
import traceback


def get_user_view(request):
    if request.method == 'GET':
        Log().debug("get user view")
        employee = get_employee(request)
        #print employee
        page = "/accounts/login/"
        if not employee:
            pass
        elif employee.post == "ad" or employee.post == "an":
            page = "/order/all"
        elif employee.post == "rs" or employee.post == "r3":
            page = "/review/mine"
        elif employee.post == "rm"  or employee.post == "r2" or employee.post == "rz":
            page = "/review/all"
        elif employee.post == "cs":
            page = "/collection/mine"
        elif employee.post == "cm"  or employee.post == "c1":
            page = "/collection/all"
        elif employee.post == "op":
            page = "/operation"
        elif employee.post == "se":
            page = "/custom"
        elif employee.post == "o1":
            page = "/operation"
        elif employee.post == "au":
            page = "/audit"
        elif employee.post == "r4":
            page = "/custom/user_view"
        return redirect(page)

@page_permission(check_employee)
def get_order_view(request):
    if request.method == 'GET':
        Log().debug("get order view")
        columns = order_views.get_order_columns()
        page= render_to_response('order/home.html', {"columns" : columns, "datatable" : [], "user" : request.user},
                                 context_instance=RequestContext(request))
        return page

@page_permission(check_employee)
def get_apply_order_view(request):
    if request.method == 'GET':
        columns = order_views.get_apply_order_columns()
        page= render_to_response('order/order_apply.html', {"columns" : columns, "datatable" : [], "user" : request.user},
                                 context_instance=RequestContext(request))
        return page

@page_permission(check_employee)
def get_promotion_view(request):
    if request.method == 'GET':
        columns = order_views.get_promotion_order_columns()
        #columns = review_views.get_review_columns()
        page= render_to_response('order/order_promotion.html', {"columns" : columns, "datatable" : [], "user" : request.user},
                                 context_instance=RequestContext(request))
        return page

@page_permission(check_employee)
def get_loan_view(request):
    if request.method == 'GET':
        columns = order_views.get_loan_order_columns()
        #columns = review_views.get_loan_columns()
        page= render_to_response('order/order_loan.html', {"columns" : columns, "datatable" : [], "user" : request.user},
                                 context_instance=RequestContext(request))
        return page

@page_permission(check_employee)
def get_collection_view(request):
    if request.method == 'GET':
        columns = order_views.get_order_columns()
        #columns = review_views.get_collection_columns()
        page= render_to_response('order/order_collection.html', {"columns" : columns, "datatable" : [], "user" : request.user},
                                 context_instance=RequestContext(request))
        return page

@page_permission(check_employee)
def get_history_view(request):
    if request.method == 'GET':
        columns = order_views.get_order_columns()
        #columns = review_views.get_collection_columns()
        page= render_to_response('order/order_history.html', {"columns" : columns, "datatable" : [], "user" : request.user},
                                 context_instance=RequestContext(request))
        return page

def clear(request):
    if request.method == 'GET':
        if request.GET.get("type") == "user":
            phone = request.GET.get("phone_no")
            Log().warn("delete user. %s" % phone)
            users = User.objects.filter(phone_no=phone);
            if len(users) == 1:
                inviters = User.objects.filter(invitation = users[0])
                print "remove inverters", len(inviters)
                for u in inviters:
                    print u.id
                    u.invitation = None
                    u.save()
                users[0].delete()
                Log().warn("delete user success %s" % phone)
            else:
                for user in users:
                    inviters = User.objects.filter(invitation = user)
                    for u in inviters:
                        print u.id
                        u.invitation = None
                        u.save()
                    user.delete()
                Log().warn("delete user failed %s. users count: %d" % (phone, len(users)))
        if request.GET.get("type") == "loan":
            order_number = request.GET.get("order_number")
            Log().warn("repay loan. %s" % order_number)
            try:
                res = risk_client.repay_loan(order_number, 0, 1)
                print res
            except Exception, e:
                traceback.print_exc()
                print e
                return HttpResponse(str(e))
    return HttpResponse("ok")

def del_all_unused_user(request):
    '''
        删除所有缺失的用户信息
    '''
    pass

def do_check_loan(request):
    '''
        计算逾期日
    '''
    if request.method == 'GET':
        date = request.GET.get("date")
        staff = get_employee(request)
        Log().warn("%s check loan %s" % (staff.username, date))
        try:
            res = risk_client.check_loan(date)
        except Exception, e:
            traceback.print_exc()
            Log().error("check loan failed %s" % str(e))
            return HttpResponse(str(e))
        return HttpResponse("ok")

