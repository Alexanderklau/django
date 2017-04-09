#!/usr/bin/env python
# coding=utf-8

from django.conf import settings
from django.shortcuts import render_to_response, get_object_or_404
from django.http import HttpResponse, HttpResponseNotAllowed, JsonResponse
from django.contrib.auth.models import User
from django.contrib import auth
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db.models import Q

from business_manager.util.permission_decorator import page_permission
from business_manager.python_common.log_client import CommonLog as Log
from business_manager.employee.models import Employee, get_employee, check_employee,\
        EmployeeGroup, PermissionSet, get_employee_platform, Platform
import traceback
import json
import static_def
from business_manager.review.models import Review
from business_manager.config_center.models import WorkFlow, WorkStatus, StatusFlow, Product
from business_manager.review import redis_client
from business_manager.employee.captcha import verify_captcha
import time

import os
import re

from business_manager.util.common_response import ImportResponse

ERR_GROUP_EXIST = -1
ERR_SERVER_INNER_FAILED = -2
ERR_ENTRY_NOT_EXIST = -3
ERR_USER_EXIST = -4
ERR_GROUP_NOT_EMPTY = -5
ERR_ENTRY_CANNOT_EDIT = -6
ERR_CAPTCHA_NOT_CORRECT = -7

WX_SESSION = 'BSM_WX_SESSION_%s'


@require_http_methods(['POST'])
@csrf_exempt
def change_password(request):
    """"""     
    body = json.loads(request.body)
    # user_id = body.get('user_id')
    old_password = body.get('old_password').strip()
    new_password = body.get('new_password').strip()

    # employee = get_object_or_404(Employee, pk=user_id)
    u = request.user
    if u.check_password(old_password):
        if 0 == len(new_password):
            return JsonResponse({
                "code": -1,
                "msg": u"密码不能为空"
            })
        u.set_password(new_password)
        u.save()
        auth.update_session_auth_hash(request, u)
        return JsonResponse({
            "code": 0,
            "msg": u"修改密码成功"
        })     
    else:      
        return JsonResponse({
            "code": -1,
            "msg": u"原始密码输入错误"
        })              


def _work_status_index(apply=None):
    workflow = WorkFlow.objects.get(pk=apply.workflow_id)
    workstatus = WorkStatus.objects.get(Q(workflow_id=apply.workflow_id) & Q(status_code=apply.status))
    statusflow_id = StatusFlow.objects.get(Q(status_id=workstatus.id) & Q(flow_id=workflow.id)).status_id
    return list(StatusFlow.objects.filter(flow_id=workflow.id).order_by('id').values_list('status_id', flat=True)).index(statusflow_id)


def get_colletion_level(employee=None):
    """返回员工对应m级别"""
    if not employee:
        return 

    groups = employee.group_list.all()
    
    levels = list()
    for g in groups:
        m_level = ''
        p = re.search(r'M(\d{1})(.*)', g.group_name)
        if not p:
            continue
        if p.group(1) and not p.group(2):
            m_level = 'm' + p.group(1)
        elif p.group(1) and p.group(2):
            m_level = 'm5+'
        if m_level:
            levels.append(m_level)
    if levels:
        return levels[0]
    return ''


def get_employee_collection_info(request):
    """"""
    if "GET" == request.method:
        # employee = get_object_or_404(Employee, pk=request.GET.get('employee_id'))
        try:
            employee = Employee.objects.get(pk=request.GET.get('employee_id'))
        except:
            employee = None
        if not employee:
            return HttpResponse(json.dumps({
                "code": -1, 
                "msg": u"该用户不存在"
            }))
        pms = employee.get_permission_list()
        is_collection_user = 0
        employee_list = list()
        for pm in pms:
            if pm.permissions and '/collection/info' in pm.permissions.split(','):
                is_collection_user = 1
                break
        if is_collection_user:
            users = Employee.objects.filter(leader=employee.id)
            for _u in users:
                _level = get_colletion_level(_u)
                employee_list.append({
                    'id': _u.id,
                    'username': _u.user.username, 
                    'realname': _u.username, 
                    'is_active': _u.user.is_active, 
                    'm_level': _level
                })
            _role = u'催收员'
            if employee.user.username == 'admin':
                _role = u'催收管理员'
            else:
                for g in employee.group_list.all():
                    for p in g.permissions.all():
                        if p.name == u'催收BI查看(主管)':
                            _role = u'催收管理员'
            return HttpResponse(json.dumps({
                "code": 0, 
                "msg": "", 
                "info": {
                    "role": _role,
                    "employee_list": employee_list
                }
            }))
        return HttpResponse(json.dumps({
            "code": -1, 
            "msg": u"该用户不具备催收权限"
        }))
    raise HttpResponseNotAllowed


def _add_step_list(employee):
    """"""
    pms = employee.get_permission_list()
    is_review_user = 0

    for pm in pms:
        if pm.permissions and '/review/action' in pm.permissions.split(','):
            is_review_user = 1
            break

    if is_review_user:
        reviews = Review.objects.filter(reviewer__id=employee.id)
        flow_list = []
        tmp_ids = []
        if reviews:
            for review in reviews:
                flow = review.order.workflow
                if flow and flow.is_in_use == 1:
                    try:
                        wss = WorkStatus.objects.filter(workflow__id=flow.id).filter(status_code=review.review_res)
                        statusflow_id = StatusFlow.objects.get(Q(status_id=wss[0].id) & Q(flow_id=review.order.workflow.id)).status_id
                        _index = list(StatusFlow.objects.filter(flow_id=review.order.workflow.id).order_by('id').values_list('status_id',flat=True)).index(statusflow_id)
                        if wss[0].id not in tmp_ids:
                            flow_list.append({
                                "id": wss[0].id,
                                "name": wss[0].other_name if wss[0].other_name else wss[0].name,
                                "is_inner": wss[0].is_inner,
                                "order": _index
                            })
                            tmp_ids.append(wss[0].id)
                    except:
                        pass
        return flow_list
    else:
        return False

def get_employee_review_info(request):
    """:return 返回所有具有审批权限的用户信息"""
    if "GET" == request.method:
        # employee = get_object_or_404(Employee, pk=request.GET.get('employee_id'))
        try:
            employee = Employee.objects.get(pk=request.GET.get('employee_id'))
        except:
            employee = None
        if not employee:
            return HttpResponse(json.dumps({
                "code": -1, 
                "msg": u"该用户不存在"
            }))
        pms = employee.get_permission_list()
        is_review_user = 0
        employee_list = list()
        for pm in pms:
            if pm.permissions and '/review/action' in pm.permissions.split(','):
                is_review_user = 1
                break
        if is_review_user:
            reviews = Review.objects.filter(reviewer__id=employee.id)
            # print(reviews)
            flow_list = []
            tmp_ids = []
            if reviews:
                # flow_list = list()
                for review in reviews:
                    flow = review.order.workflow
                    if flow and flow.is_in_use == 1:
                        # print review.review_res, review.order.workflow
                        try:
                            wss = WorkStatus.objects.filter(workflow__id=flow.id).filter(status_code=review.review_res)
                            statusflow_id = StatusFlow.objects.get(Q(status_id=wss[0].id) & Q(flow_id=review.order.workflow.id)).status_id
                            _index = list(StatusFlow.objects.filter(flow_id=review.order.workflow.id).order_by('id').values_list('status_id', flat=True)).index(statusflow_id)
                            if wss[0].id not in tmp_ids:
                                flow_list.append({
                                    "id": wss[0].id, 
                                    "name": wss[0].other_name if wss[0].other_name else wss[0].name, 
                                    "is_inner": wss[0].is_inner, 
                                    "order": _index 
                                })
                                tmp_ids.append(wss[0].id)
                        except:
                            continue
            users = Employee.objects.filter(leader=employee.id)
            for _u in users:
                _step_list = _add_step_list(_u)
                if False == _step_list:
                    continue
                employee_list.append({
                    "id": _u.id, 
                    "username": _u.user.username,
                    "realname": _u.username,
                    "step_list": _step_list or []
                })
            _role = u'审批员'
            if employee.user.username == 'admin':
                _role = u'审批管理员'
            else:
                for g in employee.group_list.all():
                    for p in g.permissions.all():
                        if p.name == u'审批BI查看(主管)':
                            _role = u'审批管理员'
            return HttpResponse(json.dumps({
                "code": 0, 
                "msg": "", 
                "info": {"role": _role, "employee_list": employee_list, "step_list": flow_list}
            }))
        return HttpResponse(json.dumps({"code": -1, "msg": u"该用户不具备审批权限"}))
    raise HttpResponseNotAllowed


@csrf_exempt
def login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        captcha = request.POST.get('captcha', '')
        user=auth.authenticate(username=username,password=password)
        if user:
            if not user.is_active:
                return HttpResponse(json.dumps({'code': ERR_ENTRY_NOT_EXIST, 'msg': u'用户名或密码错误'}))
            auth.login(request, user)
            try:
                employee = Employee.objects.get(user = user)
            except Exception, e:
                return HttpResponse(json.dumps({'code': ERR_ENTRY_NOT_EXIST, 'msg': u'用户名或密码错误'}))
            if not verify_captcha(captcha, username):
                return HttpResponse(json.dumps({'code': ERR_CAPTCHA_NOT_CORRECT, 'msg': u'验证码错误'}))
            panel = {}
            tmp = {}
            permission_list = employee.get_permission_list()
            for permission in permission_list:
                top_name = permission.belong_system_name
                sub_name = permission.belong_sub_name
                if not top_name or top_name not in static_def.panel_info:
                    continue
                if top_name in panel:
                    try:
                        if sub_name and sub_name not in tmp[top_name]:
                            panel[top_name]['sub_panel'].append({'name': sub_name, 'desc_name': static_def.panel_info[top_name]['sub_info'][sub_name]})
                            tmp[top_name].append(sub_name)
                    except Exception as e:
                        print e
                else:
                    panel[top_name] = {'top_name': top_name, 
                                       'desc_name': static_def.panel_info[top_name]['url'],
                                       'order': static_def.panel_info[top_name]['order'],
                                       'selected_icon': static_def.panel_info[top_name]['selected_icon'],
                                       'unselected_icon': static_def.panel_info[top_name]['unselected_icon']}
                    if sub_name:
                        if sub_name == u'新增订单':
                            panel[top_name]['sub_panel'] = []
                            platform = employee.platform_list.all()[0].name
                            products = Product.objects.filter(platform = platform, is_in_use = 1)
                            for product in products:
                                panel[top_name]['sub_panel'].append({'name': product.show_name,
                                                                     'desc_name': '/order/jinj_xzdd{}?product={}'.format(product.name[-1], product.name)})
                        else:
                            panel[top_name]['sub_panel'] = [{'name': sub_name,
                                                             'desc_name': static_def.panel_info[top_name]['sub_info'][sub_name]}]
                    tmp[top_name] = [sub_name]
            panel_list = panel.values()
            panel_list.sort(key = lambda p: p['order'])

            platforms = []
            account_prefix = ''
            for platform in employee.platform_list.all():
                account_prefix = platform.account_prefix
                platforms.append({'name': platform.name,
                                  'show_name': platform.show_name,
                                  'org_account': platform.org_account})

            result = {'code': 0,
                      'name': employee.username,
                      'id': employee.id,
                      'platforms': platforms,
                      'telephone': employee.telephone,
                      'account_prefix': account_prefix,
                      'main_panel': {'panel_list': panel_list}}
            return HttpResponse(json.dumps(result))
        else:
            #返回错误信息
            return HttpResponse(json.dumps({'code': ERR_ENTRY_NOT_EXIST, 'msg': u'用户名或密码错误'}))
    else:
        return render_to_response('registration/login.html')

def _check_platform(request, check_obj):
    platform = get_employee_platform(request)
    return check_obj.platform in platform

def _check_platform_list(request, check_obj):
    platform_list = get_employee_platform(request)
    for platform in check_obj.platform_list.all():
        if platform not in platform_list:
            return False
    return True

@page_permission(check_employee)
def get_main_page(request):
    if request.method == 'GET':
        employee = get_employee(request)
        permission_list = employee.get_permission_list()
        main_panel = {}
        for permission in permission_list:
            top_domain = permission.strip('/').split('/')[0]
            if top_domain not in main_panel:
                main_panel[top_domain] = static_def.panel_info[top_domain]

def _get_all_permission(selected_p):
    permission_set_list = PermissionSet.objects.filter()
    p_info_dict = {}
    for permission_set in permission_set_list:
        system_name = permission_set.belong_system_name
        if system_name not in p_info_dict:
            p_info_dict[system_name] = {'top_name': system_name,
                                        'permission_set': [{'name': permission_set.name, 
                                                            'id': permission_set.id, 
                                                            'is_choosed': 1 if permission_set.id in selected_p else 0}]}
        else:
            p_info_dict[system_name]['permission_set'].append({'name': permission_set.name, 
                                                               'id': permission_set.id,
                                                               'is_choosed': 1 if permission_set.id in selected_p else 0})
    return p_info_dict.values()


@page_permission(check_employee)
def get_all_employee_group(request):
    if request.method == 'GET':
        platform = get_employee_platform(request)
        group_list = EmployeeGroup.objects.filter(platform__in = platform.values_list('name', flat = True))
        result = []
        for group in group_list:
            count = Employee.objects.filter(group_list=group).count()
            result.append({'name': group.group_name, 
                           'id': group.id, 
                           'count': count, 
                           'group_type': group.group_type, 
                           'is_editable': group.is_editable})
        return HttpResponse(json.dumps({'code': 0, 'msg': '', 'group_list': result}))

@page_permission(check_employee)
def get_employee_group_info(request):
    if request.method == 'GET':
        group_id = request.GET.get('group_id')
        platform = get_employee_platform(request)
        group = EmployeeGroup.objects.get(pk = group_id, platform__in = platform.values_list('name', flat = True))
        if not group:
            return HttpResponse(json.dumps({'code': ERR_ENTRY_NOT_EXIST, 'msg': u'用户组不存在'}))
        group_id_list = [p.id for p in group.permissions.all()]
        permissions = _get_all_permission(group_id_list)
        result = {'code': 0, 'permissions': permissions, 'group_name': group.group_name}
        return HttpResponse(json.dumps(result))

@page_permission(check_employee)
def get_employee_group_member(request):
    if request.method == 'GET':
        group_id = request.GET.get('group_id')
        platform = get_employee_platform(request)
        group = EmployeeGroup.objects.get(pk = group_id, platform__in = platform.values_list('name', flat = True))
        if not group:
            return HttpResponse(json.dumps({'code': ERR_ENTRY_NOT_EXIST, 'msg': u'用户组不存在'}))
        employee_list = Employee.objects.filter(group_list = group)
        result = []
        for employee in employee_list:
            result.append({'realname': employee.username, 'user_id': employee.id, 'username': employee.user.username, 'is_active': employee.user.is_active})
        return HttpResponse(json.dumps({'code': 0, 'members': result}))

@csrf_exempt
@page_permission(check_employee)
def new_employee(request):
    if request.method == 'POST':
        try:
            args = request.POST.dict()
            username = args['username']
            realname = args['realname']
            id_no = args['id_no']
            mobile = args['mobile']
            telephone = args['telephone']
            leader = args['leader']
            group_list = ''
            if 'platform' in args and args['platform']:
                platform = Platform.objects.filter(pk__in = args['platform'].split(','))
            else:
                platform = get_employee_platform(request)
            user = User.objects.filter(username = username)
            if user:
                return HttpResponse(json.dumps({'code': ERR_USER_EXIST, 'msg': u'账号已存在'}))
            
            if 'group_list' in args:
                group_list = args['group_list']
                if group_list:
                    for group_id in group_list.split(','):
                        group = EmployeeGroup.objects.get(pk = group_id)
                        if group.is_editable == 0:
                            return HttpResponse(json.dumps({'code': ERR_ENTRY_CANNOT_EDIT, 'msg': u'选择的用户组不可编辑，请重新选择所属用户组'}))

            user = User.objects.create_user(username, '', id_no[-6:])
            employee = Employee.objects.filter(mobile = mobile)
            if employee:
                user.delete()
                return HttpResponse(json.dumps({'code': ERR_USER_EXIST, 'msg': u'大人，手机号码不能重复'}))
            
            eps = Employee.objects.filter(id_no=id_no)
            if eps:
                user.delete()
                return HttpResponse(json.dumps({'code': ERR_USER_EXIST, 'msg': u'大人，身份证号码不能重复'}))
            new_employee = Employee(user = user, username = realname, mobile = mobile, id_no = id_no, 
                                    telephone = telephone)
            new_employee.save()
            for p in platform:
                new_employee.platform_list.add(p)
            if 'group_list' in args:
                group_list = args['group_list']
                if group_list:
                    for group_id in group_list.split(','):
                        group = EmployeeGroup.objects.get(pk = group_id)
                        if not group:
                            continue
                        new_employee.group_list.add(group)
            print 'leader:', leader
            if leader:
                new_employee.leader = int(leader)
            new_employee.save()
            rsp = {'code': 0, 'user_id': new_employee.id}
            return HttpResponse(json.dumps(rsp))
        except Exception,e:
            rsp = {'code': ERR_SERVER_INNER_FAILED, 'msg': str(e)}
            return HttpResponse(json.dumps(rsp))

@csrf_exempt
@page_permission(check_employee)
def modify_employee(request):
    if request.method == 'POST':
        try:
            args = request.POST.dict()
            user_id = args['user_id']
            realname = args['realname']
            id_no = args['id_no']
            mobile = args['mobile']
            telephone = args['telephone']
            leader = args['leader']
            group_list = ''
            
            if 'undefined' == leader:
                leader = None

            employee = Employee.objects.filter(Q(mobile = mobile) | Q(id_no = id_no))
            if employee.count() > 1:
                return HttpResponse(json.dumps({'code': ERR_USER_EXIST, 'msg': u'用户手机号和身份证都不允许重复'}))

            employee = Employee.objects.get(pk = user_id)
            if not employee or not _check_platform_list(request, employee):
                return HttpResponse(json.dumps({'code': ERR_ENTRY_NOT_EXIST, 'msg': u'用户不存在'}))

            if employee.user.username == 'admin':
                return HttpResponse(json.dumps({'code': ERR_ENTRY_CANNOT_EDIT, 'msg': u'超级管理员不可编辑'}))

            employee.username = realname
            employee.mobile = mobile
            employee.telephone = telephone
            employee.id_no = id_no

            if 'platform' in args and args['platform'] != 'null':
                employee.platform_list.clear()
                for p in Platform.objects.filter(pk__in = args['platform'].split(',')):
                    employee.platform_list.add(p)
            if 'group_list' in args:
                group_list = args['group_list']
                if group_list:
                    group_list = group_list.split(",")
                    if group_list:
                        employee.group_list.clear()
                    for group_id in group_list:
                        group = EmployeeGroup.objects.get(pk = group_id)
                        if not group:
                            continue
                        employee.group_list.add(group)
                else:
                    employee.group_list.clear()
            else:
                employee.group_list.clear()
            if leader:
                employee.leader = int(leader)
            else:
                employee.leader = 0
            employee.save()
            rsp = {'code': 0, 'user_id': employee.id}
            return HttpResponse(json.dumps(rsp))
        except Exception,e:
            rsp = {'code': ERR_SERVER_INNER_FAILED, 'msg': str(e)}
            return HttpResponse(json.dumps(rsp))

@csrf_exempt
@page_permission(check_employee)
def reset_password(request):
    if request.method == 'POST':
        try:
            user_id = request.POST.get('user_id')
            employee = Employee.objects.filter(pk = user_id).first()
            if not employee or not _check_platform_list(request, employee):
                return HttpResponse(json.dumps({'code': ERR_ENTRY_NOT_EXIST, 'msg': u'用户不存在'}))
            user = employee.user
            user.set_password(employee.id_no[-6:])
            user.save()
            employee.save()
            return HttpResponse(json.dumps({'code': 0}))
        except Exception,e:
            return HttpResponse(json.dumps({'code': ERR_SERVER_INNER_FAILED, 'msg': str(e)}))

@csrf_exempt
@page_permission(check_employee)
def create_employee_group(request):
    if request.method == 'POST':
        try:
            group_name = request.POST.get('group_name')
            platform = get_employee_platform(request)[0]
            group = EmployeeGroup.objects.filter(group_name = group_name, platform = platform.name)
            if group:
                return HttpResponse(json.dumps({'code': ERR_GROUP_EXIST, 'msg': u'用户组{0}已存在'.format(group_name)}))
            group = EmployeeGroup(group_name = group_name, platform = platform.name)
            permissions = request.POST.get('permissions')
            if permissions:
                for permission_id in permissions.split(','):
                    permission = PermissionSet.objects.get(pk = permission_id)
                    if not permission:
                        continue
                    group.permissions.add(permission)
            group.save()
            return HttpResponse(json.dumps({'code': 0, 'group_id': group.id}))
        except Exception,e:
            return HttpResponse(json.dumps({'code': ERR_SERVER_INNER_FAILED, 'msg': str(e)}))

@csrf_exempt
@page_permission(check_employee)
def add_employee_to_group(request):
    if request.method == 'POST':
        try:
            group_id = request.POST.get('group_id')
            employee_id = request.POST.get('employee_id')
            platform = get_employee_platform(request)
            group = EmployeeGroup.objects.get(pk = group_id, platform__in = platform.values_list('name', flat = True))
            if not group:
                Log().error('add_employee_to_group failed, group or employee not exist, {0} {1}'.format(group_id, employee_id))
                return HttpResponse(json.dumps({'code': ERR_ENTRY_NOT_EXIST, 'msg': u'用户组或用户不存在'}))
            if group.is_editable == 0:
                return HttpResponse(json.dumps({'code': ERR_ENTRY_CANNOT_EDIT, 'msg': u'当前用户组不可编辑'}))
            for employee_id in employee_id.split(','):
                employee = Employee.objects.get(pk = employee_id)
                if not _check_platform_list(request, employee):
                    continue
                employee.group_list.add(group)
                employee.save()
            return HttpResponse(json.dumps({'code': 0}))
        except Exception,e:
            return HttpResponse(json.dumps({'code': ERR_SERVER_INNER_FAILED, 'msg': str(e)}))

@csrf_exempt
@page_permission(check_employee)
def remove_employee_from_group(request):
    if request.method == 'POST':
        try:
            group_id = request.POST.get('group_id')
            employee_id = request.POST.get('employee_id')
            platform = get_employee_platform(request)
            group = EmployeeGroup.objects.get(pk = group_id, platform__in = platform.values_list('name', flat = True))
            employee = Employee.objects.get(pk = employee_id)
            if not group or not employee or not _check_platform_list(request, employee):
                Log().error('add_employee_to_group failed, group or employee not exist, {0} {1}'.format(group_id, employee_id))
                return HttpResponse(json.dumps({'code': ERR_ENTRY_NOT_EXIST, 'msg': u'用户组或用户不存在'}))
            if group.is_editable == 0:
                return HttpResponse(json.dumps({'code': ERR_ENTRY_CANNOT_EDIT, 'msg': u'当前用户组不可编辑'}))
            employee.group_list.remove(group)
            employee.save()
            return HttpResponse(json.dumps({'code': 0}))
        except Exception,e:
            return HttpResponse(json.dumps({'code': ERR_SERVER_INNER_FAILED, 'msg': str(e)}))

@csrf_exempt
@page_permission(check_employee)
def modify_employee_group(request):
    if request.method == 'POST':
        try:
            group_id = request.POST.get('group_id')
            platform = get_employee_platform(request)
            group = EmployeeGroup.objects.get(pk = group_id, platform__in = platform.values_list('name', flat = True))
            if not group:
                Log().error('modify_employee_group failed, group {0} not exist'.format(group_id))
                return HttpResponse(json.dumps({'code': ERR_ENTRY_NOT_EXIST, 'msg': u'用户组不存在'}))
            if group.is_editable == 0:
                return HttpResponse(json.dumps({'code': ERR_ENTRY_CANNOT_EDIT, 'msg': u'当前用户组不可编辑'}))
            group_name = request.POST.get('group_name')
            permissions = request.POST.get('permissions')
            if permissions:
                permissions = permissions.split(',')
                group.permissions.clear()
                for permission_id in permissions:
                    permission = PermissionSet.objects.get(pk = permission_id)
                    group.permissions.add(permission)
            if group_name:
                group.group_name = group_name
            group.save()
            return HttpResponse({json.dumps({'code': 0})})
        except Exception,e:
            return HttpResponse(json.dumps({'code': ERR_SERVER_INNER_FAILED, 'msg': str(e)}))

@csrf_exempt
@page_permission(check_employee)
def delete_employee_group(request):
    if request.method == 'POST':
        try:
            group_id = request.POST.get('group_id')
            platform = get_employee_platform(request)
            group = EmployeeGroup.objects.get(pk = group_id, platform__in = platform.values_list('name', flat = True))
            if not group:
                return HttpResponse(json.dumps({'code': ERR_ENTRY_NOT_EXIST, 'msg': u'用户组不存在'}))
            if group.is_editable == 0:
                return HttpResponse(json.dumps({'code': ERR_ENTRY_CANNOT_EDIT, 'msg': u'当前用户组不可编辑'}))
            employee = Employee.objects.filter(group_list = group)
            if employee:
                return HttpResponse(json.dumps({'code': ERR_GROUP_NOT_EMPTY, 'msg': u'用户组仍有员工，删除失败'}))
            group.delete()
            return HttpResponse(json.dumps({'code': 0}))
        except Exception,e:
            return HttpResponse(json.dumps({'code': ERR_SERVER_INNER_FAILED, 'msg': str(e)}))

def _pagination(request=None, queryset=None):
    """分页"""
    page, page_size = request.GET.get('page'), request.GET.get('page_size')
    if page and page_size:
        start = int(page) * int(page_size)
        return queryset[start-int(page_size):start]
    return queryset

@page_permission(check_employee)
def search_employee(request):
    if request.method == 'GET':
        try:
            key = request.GET.get('key')
            key = key.strip()
            platform_param = request.GET.get('platform')
            if platform_param and platform_param != 'all':
                platform = Platform.objects.filter(pk__in = platform_param.split(','))
            else:
                platform = get_employee_platform(request)
            if key:
                print 'get user'
                user = User.objects.filter(username = key).first()
                if user:
                    employee = Employee.objects.filter(user = user, platform_list__in = platform).first()
                    if employee:
                        group_name = ','.join([g.group_name for g in employee.group_list.all()])
                        platform = ','.join([p.show_name for p in employee.platform_list.all()])
                        return HttpResponse(json.dumps({'code': 0, 'employee_list': [{'username': key,
                                                                                      'telephone': employee.telephone,
                                                                                      'realname': employee.username,
                                                                                      'group': group_name,
                                                                                      'is_active': user.is_active,
                                                                                      'platform': platform,
                                                                                      'id': employee.id}]}))
            query_platform = Q(platform_list__in = platform)
            if key:
                query_name = Q(username__startswith=key)
                query_mobile = Q(mobile = key)
                query_id = Q(id_no = key)
                _search_result = Employee.objects.filter((query_name | query_mobile | query_id) & query_platform).order_by('-id')
            else:
                _search_result = Employee.objects.filter(query_platform).order_by('-id')
            
            results = None
            order_name, order_way = request.GET.get('order_name', '').strip(), request.GET.get('order_way', '').strip()
            if order_name and order_way:
                if 'asc' == order_way:
                    results = _search_result.order_by('user__date_joined')
                elif 'desc' == order_way:
                    results = _search_result.order_by('-user__date_joined')
            if results:
                search_result = _pagination(request, results)
            else:
                search_result = _pagination(request, _search_result)
            employee_list = []
            for e in search_result:
                group_name = ','.join([g.group_name for g in e.group_list.all()])
                platform = ','.join([p.show_name for p in e.platform_list.all()])
                employee_list.append({'username': e.user.username,
                                      'realname': e.username,
                                      'group': group_name,
                                      'created_at': e.user.date_joined.strftime('%Y-%m-%d %H:%M:%S') if e.user else '',
                                      'is_active': e.user.is_active,
                                      'telephone': e.telephone,
                                      'platform': platform,
                                      'id': e.id})
            return HttpResponse(json.dumps({'code': 0, 'employee_count': _search_result.count(), 'employee_list': employee_list}))
        except Exception,e:
            print e
            return HttpResponse(json.dumps({}))

@page_permission(check_employee)
def employee_statistic(request):
    if request.method == 'GET':
        platform = get_employee_platform(request)
        employee_count = Employee.objects.filter(platform_list__in = platform).count()
        employee_list = Employee.objects.filter(platform_list__in = platform).order_by('-id')
        #yesterday = get_yestoday()
        #yesterday = datetime.strptime(str(yesterday), '%Y-%m-%d')
        new_employee = []
        for i,employee in enumerate(employee_list):
            if i == 3:
                break
            new_employee.append(employee.username)
        group_list = EmployeeGroup.objects.filter(platform__in = platform.values_list('name', flat = True))
        group_info = []
        for group in group_list:
            count = Employee.objects.filter(group_list = group).count()
            group_info.append({'group_name': group.group_name, 'count': count})
        return HttpResponse(json.dumps({'employee_count': employee_count,
                                        'new_employee': ','.join(new_employee),
                                        'group': group_info,
                                        'code': 0}))

@page_permission(check_employee)
def get_employee_info(request):
    if request.method == 'GET':
        try:
            user_id = request.GET.get('user_id')
            employee = Employee.objects.filter(pk = user_id).first()
            if not employee or not _check_platform_list(request, employee):
                return HttpResponse(json.dumps({'code': ERR_ENTRY_NOT_EXIST, 'msg': u'用户不存在'}))
            result = {'user_id': user_id,
                      'realname': employee.username,
                      'username': employee.user.username,
                      'id_no': employee.id_no,
                      'phone': employee.mobile,
                      'telephone': employee.telephone,
                      'group': [],
                      'code': 0,
                      'platforms': [{'name': p.name, 'show_name': p.show_name} for p in employee.platform_list.all()]}
            if employee.leader:
                leader = Employee.objects.filter(pk = employee.leader).first()
                result['leader_id'] = leader.id
                result['leader_name'] = leader.username
            for group in employee.group_list.all():
                result['group'].append({'id': group.id, 'name': group.group_name})
            return HttpResponse(json.dumps(result))
        except Exception,e:
            return HttpResponse(json.dumps({'code': ERR_SERVER_INNER_FAILED, 'msg': str(e)}))

@csrf_exempt
@page_permission(check_employee)
def change_employee_status(request):
    if request.method == 'POST':
        try:
            user_id = request.POST.get('user_id')
            status = request.POST.get('status')
            employee = Employee.objects.filter(pk = user_id).first()
            if not employee or not _check_platform_list(request, employee):
                return HttpResponse(json.dumps({'code': ERR_ENTRY_NOT_EXIST, 'msg': u'用户不存在'}))
            employee.user.is_active = int(status)
            employee.user.save()
            employee.save()
            return HttpResponse(json.dumps({'code': 0}))
        except Exception,e:
            return HttpResponse(json.dumps({'code': ERR_SERVER_INNER_FAILED, 'msg': str(e)}))

def _gen_session():
    return ''.join(map(lambda xx:(hex(ord(xx))[2:]),os.urandom(16)))

@csrf_exempt
def wx_get_session(request):
    if request.method == 'POST':
        try:
            username = request.POST.get('username')
            user = User.objects.get(username = username)
            if not user:
                return HttpResponse(json.dumps({'code': ERR_ENTRY_NOT_EXIST, 'msg': u'用户不存在'}))
            employee = Employee.objects.get(user = user)
            if not employee:
                return HttpResponse(json.dumps({'code': ERR_ENTRY_NOT_EXIST, 'msg': u'用户不存在'}))
            session = _gen_session()
            redis_client.set(WX_SESSION % session, json.dumps({'employee_id': employee.id, 'time': int(time.time())}))
            return HttpResponse(json.dumps({'code': 0, 'session': session}))
        except Exception,e:
            return HttpResponse(json.dumps({'code': ERR_SERVER_INNER_FAILED, 'msg': str(e)}))

def check_wx_session(session):
    session_info = redis_client.get(WX_SESSION % session)
    if not session_info:
        return None
    session_info = json.loads(session_info)
    timestamp = session_info['time']
    curr_time = int(time.time())
    if curr_time - timestamp > settings.WX_SESSION_TIMEOUT_S:
        return None
    session_info['time'] = curr_time
    redis_client.set(WX_SESSION % session, json.dumps(session_info))
    return session_info['employee_id']


def get_all_employee_group_info(request):
    platform = get_employee_platform(request)[0].name
    groups = EmployeeGroup.objects.filter(platform = platform)
    data = []
    for group in groups:
        group_member = Employee.objects.filter(group_list__in=[group], user__is_active=True)
        group_count = len(group_member)
        group_member = [item.username for item in group_member]
        data.append(
            {
                "group_name": group.group_name,
                "group_id": group.id,
                "group_count": group_count,
                "group_member": group_member,
            }
        )
    return ImportResponse.success(data=data)



















