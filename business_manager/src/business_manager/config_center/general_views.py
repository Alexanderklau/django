#!/usr/bin/env python
# coding=utf-8

from django.http import HttpResponse, HttpResponseNotAllowed
from business_manager.util.permission_decorator import page_permission
from business_manager.employee.models import get_employee, get_employee_platform, Platform
from business_manager.config_center.models import *
from business_manager.python_common.log_client import CommonLog as Log
from django.db.models import Q
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render_to_response
from business_manager.employee.models import check_employee
from business_manager.review import redis_client
import json
import copy

CALL_PASS_LINE_KEY = 'call_pass_line_%s'

@csrf_exempt
@page_permission(check_employee)
def get_active_workflow(request):
    """:return 返回当前工作流审批阶段列表"""
    if request.method == "GET":
        platform = get_employee_platform(request).values_list('name', flat = True)
        print platform
        wss = list()
        workflow = WorkFlow.objects.filter(Q(is_delete=0) & Q(is_in_use=1) & Q(platform__in = platform)).first()
        ws = WorkStatus.objects.filter(is_delete=0).filter(Q(workflow = workflow) & Q(platform__in = platform))
        for work_status in ws:
            try:
                statusflow_id = StatusFlow.objects.get(Q(status_id=work_status.id) & Q(flow_id=workflow.id)).status_id
                _index = list(StatusFlow.objects.filter(flow_id=workflow.id).order_by('id').values_list('status_id', flat=True)).index(statusflow_id)
                wss.append({
                    "id": work_status.id, 
                    "name": work_status.other_name if work_status.other_name else work_status.name,
                    "is_inner": work_status.is_inner,
                    "order": _index
                })
            except:
                continue

        return HttpResponse(json.dumps({"code": 0, "msg": "", "step_list": wss}))
    raise HttpResponseNotAllowed


def get_config_view(request):
    if request.method == 'GET':
        Log().debug('get config view')
        employee = get_employee(request)
        page = "/accounts/login/"
        if not employee:
            pass
        elif employee.post == 'ad' or employee.post == "an":
            page = 'config_center/all'
        return render_to_response(page)


@csrf_exempt
@page_permission(check_employee)
def add_field(request):
    if request.method == 'POST':
        post_data = request.POST
        show_name = post_data.get("show_name")
        desc = post_data.get("desc")
        field_type = post_data.get('type')
        field_value = post_data.get('reserve')
        platform = get_employee_platform(request)[0].name

        if show_name and field_type:
            show_name_query = Q(show_name=show_name)
            is_delete_query = Q(is_delete=0)
            platform_query = Q(platform = platform)
            same_name_count = ProfileField.objects.filter(show_name_query & is_delete_query & platform_query).count()
            if same_name_count > 0:
                return HttpResponse(json.dumps({'code': -1, "msg":"字段名已存在，请跟换。", 'field_id': "", "is_inner":0, "is_in_use":0}))
            elif same_name_count == 0:
                new_field = ProfileField()
                new_field.description = desc
                new_field.show_name = show_name
                new_field.type = field_type
                if field_value:
                    new_field.reserve = field_value
                new_field.save()
                new_field.name = 'new_field_' + str(new_field.id)
                new_field.platform = platform
                new_field.save()
                return HttpResponse(json.dumps({'code': 0, "msg":"" ,'field_id': new_field.id, "is_inner":0, "is_in_use":0}))
        else:
            return HttpResponse(json.dumps({'code': -1, "msg":"请完整填写信息", 'field_id': "", "is_inner":0, "is_in_use":0}))

@csrf_exempt
@page_permission(check_employee)
def delete_field(request):
    if request.method == "POST":
        field_id = request.POST.get("field_id")
        platform = get_employee_platform(request)[0].name
        field = ProfileField.objects.get(id=field_id, platform = platform)
        if not field:
            return HttpResponse(json.dumps({'code': -1, 'msg': u'字段不存在'}))
        if field.is_in_use == 0 and field.is_inner == 0:
            field.is_delete = 1
            field.save()
            return HttpResponse(json.dumps({'code': 0, 'msg': ""}))
        elif field.is_in_use == 1 or field.is_inner == 1:
            return HttpResponse(json.dumps({'code': -1, 'msg': "不能删除该字段，字段正在使用或为内置字段"}))


@csrf_exempt
@page_permission(check_employee)
def update_field(request):
    if request.method == "POST":
        def _update_field(field, desc, field_type, field_reserve):
            if desc:
                field.description = desc
            if field_reserve:
                field.reserve = field_reserve
            field.type = field_type
            field.save()

        post_data = request.POST
        show_name = post_data.get("show_name")
        field_id = post_data.get("field_id")
        desc = post_data.get("desc")
        field_type = post_data.get("type")
        field_reserve = post_data.get("reserve")
        platform = get_employee_platform(request)[0].name

        if show_name and field_type:
            field = ProfileField.objects.get(id=field_id, platform = platform)
            if not field:
                return HttpResponse(json.dumps({'code': -1, 'msg': '字段不存在'}))
            show_name_query = Q(show_name=show_name)
            is_delete_query = Q(is_delete=0)
            same_name_field_set = ProfileField.objects.filter(show_name_query & is_delete_query)
            if field.is_inner == 1 or field.is_in_use == 1:
                return HttpResponse(json.dumps({'code': -1, 'msg': "不能修改该字段，字段正在使用或为内置字段"}))
            elif same_name_field_set.count() > 0:
                if same_name_field_set[0].id == field.id:
                    if field.is_inner == 0 and field.is_in_use == 0:
                        _update_field(field, desc, field_type, field_reserve)
                        return HttpResponse(json.dumps({'code': 0, 'msg': "修改成功", 'field_id': field.id, "is_inner":0, "is_in_use":0}))
                elif same_name_field_set[0].id != field.id:
                    return HttpResponse(json.dumps({'code': -1, 'msg': "该字段名已存在，请换一个名字。"}))
                elif same_name_field_set[0].id == field.id:
                    _update_field(field, desc, field_type, field_reserve)
                    return HttpResponse(json.dumps({'code': 0, 'msg': "修改成功", 'field_id': field.id, "is_inner":0, "is_in_use":0}))
            elif same_name_field_set.count() == 0:
                if field.is_inner == 0 and field.is_in_use == 0:
                    _update_field(field, desc, field_type, field_reserve)
                    return HttpResponse(json.dumps({'code': 0, 'msg': "修改成功", 'field_id': field.id, "is_inner":0, "is_in_use":0}))
        else:
            return HttpResponse(json.dumps({'code': -1, "msg":"请完整填写信息", 'field_id': "", "is_inner":0, "is_in_use":0}))


@csrf_exempt
@page_permission(check_employee)
def get_fields(request):
    if request.method == "GET":
        try:
            post_data = request.GET
            modules_id = post_data.get("modules_id")
            result_list = []
            platform = get_employee_platform(request)
            print platform
            platform = platform.values_list('name', flat = True)
            if modules_id:
                modules_id = map(int, modules_id.split(','))
                modules = ProfileModule.objects.filter(id__in = modules_id, platform__in = platform)
                print modules
                for module in modules:
                    if module.required_fields:
                        for field_dict in json.loads(module.required_fields):
                            field = ProfileField.objects.get(id=int(field_dict.get("field_id")))
                            if field.is_delete == 0:
                                result_list.append({"show_name":field.show_name , "field_id":field.id, "description":field.description, "type":field.type, "reserve":field.reserve, "is_inner":field.is_inner, "is_in_use":field.is_in_use, "is_must":field_dict.get("is_must")})
                    else:
                        return HttpResponse(json.dumps({"code":-1, "msg":"模块没有字段", 'fields': ''}))
                return HttpResponse(json.dumps({"code": 0, "msg": "", "fields": result_list}))
            else :
                page_number = int(request.GET.get('page', '0'))
                page_size = int(request.GET.get('page_size', '0'))
                start = page_number * page_size
                sort_way = request.GET.get('sort_way')
                if sort_way == 'asc':
                    fields = ProfileField.objects.filter(is_delete=0, platform__in = platform).order_by('id')
                else:
                    fields = ProfileField.objects.filter(is_delete=0, platform__in = platform).order_by('-id')
                field_count = fields.count()
                print field_count
                if page_size != 0:
                    fields = fields[start - page_size:start]
                for field in fields:
                    result_list.append({"show_name":field.show_name , "field_id":field.id, "description":field.description, "type":field.type, "reserve":field.reserve, "is_inner":field.is_inner, "is_in_use":field.is_in_use})
                return HttpResponse(json.dumps({"code":0, "msg":"", 'fields': result_list, 'field_count':field_count}))
        except Exception,e:
            print e
            return HttpResponse(json.dumps({"code":1, "msg":str(e)}))


@csrf_exempt
@page_permission(check_employee)
def search_field(request):
    if request.method == "GET":
        platform = get_employee_platform(request).values_list('name', flat = True)
        field_id = request.GET.get("field_id")
        field = ProfileField.objects.get(id=field_id, platform__in = platform)
        if field.is_delete == 0:
            return HttpResponse(json.dumps({'code':0, 'msg':'', "field_id":field.id ,"show_name":field.show_name, "desc":field.description, "type":field.type, "reserve":field.reserve, "is_inner":field.is_inner, "is_in_use":field.is_in_use}))
        elif field.is_delete == 1:
            return HttpResponse(json.dumps({'code':0, 'msg':'', "field_id":'',"show_name":'', "desc":'', "type":'', "reserve":'', "is_inner":'', "is_in_use":''}))



@csrf_exempt
@page_permission(check_employee)
def search_field_by_name(request):
    if request.method == "GET":
        platform = get_employee_platform(request).values_list('name', flat = True)
        show_name = request.GET.get('show_name')
        fields = ProfileField.objects.filter(show_name__contains = show_name, platform__in = platform)
        result_list = []
        if fields:
            for field in fields:
                if field.is_delete == 0:
                    result_list.append({'field_id':field.id, 'show_name':field.show_name, 'desc':field.description, 'type':field.type, 'reserve':field.reserve, 'is_inner':field.is_inner, 'is_in_use':field.is_in_use})
        return HttpResponse(json.dumps({'code':0, 'msg':'', 'fields':result_list}))



@csrf_exempt
@page_permission(check_employee)
def add_module(request):
    if request.method == "POST":
        desc = request.POST.get("desc")
        show_name = request.POST.get("show_name")
        platform = get_employee_platform(request)[0].name
        if show_name:
            show_name_query = Q(show_name=show_name)
            is_delete_query = Q(is_delete=0)
            platform_query = Q(platform = platform)
            same_name_module_set = ProfileModule.objects.filter(show_name_query & is_delete_query & platform_query)
            if same_name_module_set.count() == 0:
                try:
                    new_module = ProfileModule()
                    new_module.description = desc
                    new_module.show_name = show_name
                    new_module.platform = platform
                    new_module.save()
                except:
                    return HttpResponse(json.dumps({'code': -1, 'msg': "名称，备注分别不能超过6个和100个字", "module_id": "", "is_inner": 0, "is_in_use": 0}))
                return HttpResponse(json.dumps({'code': 0, 'msg': "", "module_id":new_module.id, "is_inner":0, "is_in_use":0}))
            elif same_name_module_set.count() > 0 and same_name_module_set[0].is_delete == 0:
                return HttpResponse(json.dumps({'code': -1, 'msg': "模块名已存在，请换一个模块名。", "module_id":"", "is_inner":0, "is_in_use":0}))
        else:
            return HttpResponse(json.dumps({'code': -1, 'msg': "请完整填写信息", "module_id":"", "is_inner":0, "is_in_use":0}))


@csrf_exempt
@page_permission(check_employee)
def add_new_module_in(request):
    if request.method == "POST":
        post_data = request.POST
        show_name = post_data.get('show_name')
        desc = post_data.get('desc')
        fields_id = json.loads(post_data.get("fields_id"))
        platform = get_employee_platform(request)[0].name

        if show_name and fields_id:
            if ProfileModule.objects.filter(show_name=show_name, platform = platform).count() == 0:
                module = ProfileModule()
                module.show_name = show_name
                module.description = desc
                module.required_fields = fields_id
                module.platform = platform
                module.save()
                return HttpResponse(json.dumps({'code': 0, 'msg': "", "module_id":module.id, 'show_name': module.show_name, 'desc':module.description, 'fields_id':module.required_fields, "is_inner":0, "is_in_use":0}))
            else:
                return HttpResponse(json.dumps({'code': -1, 'msg': "模块名已存在，请换一个模块名。", "module_id":"", "is_inner":0, "is_in_use":0}))
        else:
            return HttpResponse(json.dumps({'code': -1, 'msg':'请填写完整信息。', "module_id":'', 'show_name':'', 'desc':'', 'fields_id':'', "is_inner":0, "is_in_use":0}))


@csrf_exempt
@page_permission(check_employee)
def update_module(request):
    if request.method == "POST":

        def _update_module(module, desc, show_name, fields_id):
            if desc:
                module.description = desc
            module.show_name = show_name
            if fields_id:
                module.required_fields = fields_id
            module.save()

        post_data = request.POST
        module_id = post_data.get("module_id")
        desc = post_data.get("desc")
        show_name = post_data.get("show_name")
        fields_id = json.loads(post_data.get("fields_id"))
        platform = get_employee_platform(request)[0].name

        show_name_query = Q(show_name=show_name)
        is_delete_query = Q(is_delete=0)
        platform_query = Q(platform = platform)
        same_name_module_set = ProfileModule.objects.filter(is_delete_query & show_name_query & platform_query)
        module = ProfileModule.objects.get(id=module_id, platform = platform)
        if not module:
            return HttpResponse(json.dumps({'code': -1, 'msg': '模块不存在'}))

        if show_name and fields_id:
            if same_name_module_set.count() == 0:
                if module.is_inner == 0 and module.is_in_use == 0:
                    _update_module(module, desc, show_name, fields_id)
                    return HttpResponse(json.dumps({"module_id":module.id, 'code': 0, "msg":"", "is_inner":0, "is_in_use":0}))
                elif module.is_inner == 1 or module.is_in_use == 1:
                    return HttpResponse(json.dumps({"module_id":"", 'code': -1, "msg":"模块正在使用中，不能进行更新。", "is_inner":0, "is_in_use":0}))
            elif same_name_module_set.count() > 0:
                if same_name_module_set[0].id == module.id:
                    _update_module(module, desc, show_name, fields_id)
                    return HttpResponse(json.dumps({"module_id":module.id, 'code': 0, "msg":"", "is_inner":0, "is_in_use":0}))
                elif same_name_module_set[0].id != module.id and same_name_module_set[0].is_delete == 0:
                    return HttpResponse(json.dumps({"module_id":"", 'code': -1, "msg":"已有模块正在使用该名称，请更换名称。", "is_inner":0, "is_in_use":0}))
                elif same_name_module_set[0].id != module.id and same_name_module_set[0].is_delete == 1:
                    _update_module(module, desc, show_name, fields_id)
                    return HttpResponse(json.dumps({"module_id":module.id, 'code': 0, "msg":"", "is_inner":0, "is_in_use":0}))
        elif fields_id:
            if module.is_inner == 0 and module.is_in_use == 0:
                module.required_fields = fields_id
                module.save()
                return HttpResponse(json.dumps({"module_id":module.id, 'code': 0, "msg":"", "is_inner":0, "is_in_use":0}))
        else:
            return HttpResponse(json.dumps({"module_id":"", 'code': -1, "msg":"请完成填写信息", "is_inner":0, "is_in_use":0}))


@csrf_exempt
@page_permission(check_employee)
def delete_module(request):
    if request.method == "POST":
        module_id = request.POST.get("module_id")
        platform = get_employee_platform(request)[0].name
        module = ProfileModule.objects.get(id=module_id, platform = platform)
        if not module:
            return HttpResponse(json.dumps({'code': -1, 'msg': '模块不存在'}))
        if module.is_inner == 0 and module.is_in_use == 0:
            module.is_delete = 1
            module.save()
            return HttpResponse(json.dumps({'code': 0, 'msg': ""}))
        elif module.is_inner == 1 or module.is_in_use == 1:
            return HttpResponse(json.dumps({'code': -1, 'msg': "不能修改该模块，模块正在使用或为内置模块"}))



@csrf_exempt
@page_permission(check_employee)
def get_modules(request):
    if request.method == "GET":
        # post_data = json.loads(request.body)
        post_data = request.GET
        templates_id = post_data.get("templates_id")
        platform = get_employee_platform(request).values_list('name', flat = True)
        print 'platform -->', platform
        result_list = []
        print '----------------------'
        module_count = 0
        if templates_id:
            templates_id = map(int, templates_id.split(','))
            templates = ProfileFlow.objects.filter(id__in = templates_id, platform__in = platform)
            for template in templates:
                if template.required_modules:
                    for module_id in template.required_modules.split(','):
                        module = ProfileModule.objects.get(id=int(module_id))
                        if module.is_delete == 0:
                            module_count += 1
                            result_list.append({"module_id":module.id, "show_name":module.show_name, "desc":module.description, "is_inner":module.is_inner, "is_in_use":module.is_in_use})
                else:
                    return HttpResponse(json.dumps({"code":-1, "msg":"空模板，请给模板添加模块。", 'modules': ""}))
        else:
            page_number = int(request.GET.get('page', '0'))
            page_size = int(request.GET.get('page_size', '0'))
            start = page_number * page_size
            sort_way = request.GET.get('sort_way')
            if sort_way == 'asc':
                modules = ProfileModule.objects.filter(is_delete=0, platform__in = platform).order_by('id')
            else:
                modules = ProfileModule.objects.filter(is_delete=0, platform__in = platform).order_by('-id')
            module_count = modules.count()
            if page_size != 0:
                modules = modules[start - page_size:start]
            for module in modules:
                result_list.append({"module_id":module.id, "show_name":module.show_name, "desc":module.description, "is_inner":module.is_inner, "is_in_use":module.is_in_use})

        return HttpResponse(json.dumps({"code":0, "msg":"", 'modules': result_list, "module_count": module_count}))


@csrf_exempt
@page_permission(check_employee)
def search_module_by_name(request):
    if request.method == "GET":
        show_name = request.GET.get('show_name')
        platform = get_employee_platform(request).values_list('name', flat = True)
        modules = ProfileModule.objects.filter(show_name__like = show_name, platform__in = platform)
        result_list = []
        if modules:
            for module in modules:
                if module.is_delete == 0:
                    result_list.append({'module_id':module.id, 'show_name':module.show_name, 'desc':module.description, 'required_fields':module.required_fields, 'is_inner':module.is_inner, 'is_in_use':module.is_in_use, 'is_delete':module.is_delete})
        else:
            return HttpResponse(json.dumps({'code':0, 'msg':'', 'modules':''}))

        return HttpResponse(json.dumps({'code':0, 'msg':'', 'modules':result_list}))


@csrf_exempt
@page_permission(check_employee)
def add_template(request):
    if request.method == "POST":
        desc = request.POST.get("desc")
        show_name = request.POST.get("show_name")
        belong = request.POST.get("belong_system")
        platform = get_employee_platform(request)[0].name
        product = request.POST.get('product')
        if show_name:
            show_name_query = Q(show_name=show_name)
            is_delete_query = Q(is_delete=0)
            platform_query = Q(platform = platform)
            same_name_template_set = ProfileFlow.objects.filter(show_name_query & is_delete_query & platform_query)
            if same_name_template_set.count() == 0:
                template = ProfileFlow()
                template.description = desc
                template.show_name = show_name
                template.belong_system = belong
                template.platform = platform
                template.belong_product = product
                template.save()
                return HttpResponse(json.dumps({'code':0, "module_id":template.id, "msg":"", "is_in_use":0}))
            elif same_name_template_set.count() > 0 and same_name_template_set[0].is_delete == 0:
                return HttpResponse(json.dumps({'code':-1, "module_id":"", "msg":"模板名已存在，请更换模板名。", "is_in_use":0}))
        else:
            return HttpResponse(json.dumps({'code':-1, "module_id":"", "msg":"请完成填写信息", "is_in_use":0}))


@csrf_exempt
@page_permission(check_employee)
def update_template(request):
    #TODO: fix this function
    if request.method == "POST":
        def _update_template(template, desc, show_name, modules_id):
            if desc:
                template.desc = desc
            template.show_name = show_name
            if modules_id:
                template.required_modules = modules_id
            template.save()

        post_data = request.POST
        template_id = post_data.get("template_id")
        show_name = post_data.get("show_name")
        desc = post_data.get("desc")
        modules_id = post_data.get("modules_id")
        platform = get_employee_platform(request)[0].name

        template = None if template_id is None else ProfileFlow.objects.get(id = template_id, platform = platform)
        if template is None:
            return HttpResponse(json.dumps({'code':-1, "msg":"模板为空"}))

        if show_name and modules_id:
            show_name_query = Q(show_name=show_name)
            is_delete_query = Q(is_delete=0)
            same_name_template_set = ProfileFlow.objects.filter(show_name_query & is_delete_query)
            if same_name_template_set.count() == 0:
                if template.is_in_use == 0:
                    _update_template(template, desc, show_name, modules_id)
                    return HttpResponse(json.dumps({'code':0, 'module_id':template.id, "msg":"", "is_in_use":0}))
                elif template.is_in_use == 1:
                    return HttpResponse(json.dumps({'code':-1, 'module_id':"", "msg":"不能修改该模块，模板正在使用或为内置模块", "is_in_use":1}))
            if same_name_template_set.count() > 0:
                if same_name_template_set[0].id == template.id:
                    _update_template(template, desc, show_name, modules_id)
                    return HttpResponse(json.dumps({'code':0, 'module_id':template.id, "msg":"", "is_in_use":0}))
                elif same_name_template_set[0].id != template.id and same_name_template_set[0].is_delete == 0:
                    return HttpResponse(json.dumps({'code':-1, 'module_id':"", "msg":"模板名已存在，请更换模板名。", "is_in_use":1}))
                elif same_name_template_set[0].id != template.id and same_name_template_set[0].is_delete == 1:
                    _update_template(template, desc, show_name, modules_id)
                    return HttpResponse(json.dumps({'code':0, 'module_id':template.id, "msg":"", "is_in_use":0}))
        else:
            if show_name:
                if not modules_id:
                    template.required_modules = ""
                    template.save()
                return HttpResponse(json.dumps({'code':0, "msg": "保存成功"}))
            return HttpResponse(json.dumps({'code':-1, 'module_id':"", "msg":"模板名和模板内模块不能为空，请完成信息。", "is_in_use":1}))



@csrf_exempt
@page_permission(check_employee)
def get_templates(request):
    if request.method == "GET":
        templates_id = request.GET.get("templates_id")
        platform = get_employee_platform(request).values_list('name', flat = True)
        result_list = []
        if templates_id:
            templates_id = map(int, templates_id.split(','))
            templates = ProfileFlow.objects.filter(id__in = templates_id, platform__in = platform)
            for template in templates:
                if template.is_delete == 0:
                    if not template.belong_product:
                        continue
                    product = Product.objects.get(name = template.belong_product, platform = template.platform)
                    result_list.append({"template_id":template.id, 
                                        "show_name":teplate.show_name,
                                        "desc":template.description, 
                                        "is_in_use":template.is_in_use, 
                                        "belong_system":template.belong_system,
                                        'product': product.name,
                                        'product_name': product.show_name})
        else :
            templates = ProfileFlow.objects.filter(is_delete=0, platform__in = platform)
            for template in templates:
                if not template.belong_product:
                    continue
                product = Product.objects.get(name = template.belong_product, platform = template.platform)
                result_list.append({"template_id":template.id, 
                                    "show_name":template.show_name,
                                    "desc":template.description, 
                                    "is_in_use":template.is_in_use, 
                                    "belong_system":template.belong_system,
                                    'product': product.name,
                                    'product_name': product.show_name})
        return HttpResponse(json.dumps({"code":0, "msg":"", 'modules':result_list}))


@csrf_exempt
@page_permission(check_employee)
def delete_template(request):
    if request.method == "POST":
        template_id = request.POST.get("template_id")
        platform = get_employee_platform(request)[0].name
        template = ProfileFlow.objects.get(id=template_id, platform = platform)
        if not template:
            return HttpResponse(json.dumps({'code': -1, 'msg': '模板不存在'}))
        if template.is_in_use == 1:
            return HttpResponse(json.dumps({'code':-1, 'template_id':"", "msg":"不能删除该模板，模板正在使用", "is_in_use":1}))
        elif template.is_in_use == 0:
            template.is_delete = 1
            template.save()
            return HttpResponse(json.dumps({'code': 0, 'msg': ""}))

def _count_times(template):
    if not template.required_modules:
        return HttpResponse(json.dumps({'code': -1, 'msg': "该模板没有相应模块", "template_id":template.id, "is_in_use":0}))
    for module_id in template.required_modules.split(','):
        module = ProfileModule.objects.get(id=int(module_id))
        if not module.required_fields:
            return HttpResponse(json.dumps({'code': -1, 'msg': "有空模块，请完善模块", "template_id":template.id, "is_in_use":0}))
        if module.is_in_use == 0:
            module.is_in_use = 1
            module.use_times += 1
            module.save()
            for field_dict in json.loads(module.required_fields):
                field = ProfileField.objects.get(id=int(field_dict.get("field_id")))
                if field.is_in_use == 0:
                    field.is_in_use = 1
                    field.use_times += 1
                    field.save()
                elif field.is_in_use == 1:
                    field.use_times += 1
                    field.save()
        elif module.is_in_use == 1:
            module.use_times += 1
            module.save()
            for field_dict in json.loads(module.required_fields):
                field = ProfileField.objects.get(id=int(field_dict.get("field_id")))
                if field.is_in_use == 0:
                    field.is_in_use = 1
                    field.use_times += 1
                    field.save()
                elif field.is_in_use == 1:
                    field.use_times += 1
                    field.save()

@csrf_exempt
@page_permission(check_employee)
def use_template(request):
    if request.method == "POST":

        template_id = request.POST.get("template_id")
        platform = get_employee_platform(request)[0].name
        template = ProfileFlow.objects.get(id = template_id, platform = platform)
        if not template:
            return HttpResponse(json.dumps({'code': -1, 'msg': '模板不存在'}))
        using_template = ProfileFlow.objects.filter(is_in_use = 1, belong_system = u'进件子系统',
                                                   belong_product = template.belong_product, platform = platform)
        if template.required_modules:
            if using_template.count() > 0 and using_template[0].id == template.id:
                return HttpResponse(json.dumps({'code': 0, 'msg': "", "template_id":template.id, "is_in_use":1}))
            elif using_template.count() == 0 :
                template.is_in_use = 1
                _count_times(template)
                template.save()
                return HttpResponse(json.dumps({'code': 0, 'msg': "", "template_id":template.id, "is_in_use":1}))

            elif using_template.count() > 0 and using_template[0].id != template.id:
                # using_template_obj = using_template[0]
                # count_times(template)
                # using_template_obj.is_in_use = 0
                # using_template_obj.save()
                # template.is_in_use = 1
                # template.save()
                return HttpResponse(json.dumps({'code': -1, 'msg': "当前有模板正在使用，请先停用后再启用新模板。", "template_id":template.id, "is_in_use":1}))
        elif not template.required_modules:
            return HttpResponse(json.dumps({'code': -1, 'msg': "空模板。请添加模块。", "template_id":template.id, "is_in_use":0}))


@csrf_exempt
@page_permission(check_employee)
def abandon_template(request):
    if request.method == "POST":
        template_id = request.POST.get("template_id")
        platform = get_employee_platform(request)[0].name
        template = ProfileFlow.objects.get(id = template_id, platform = platform)
        if not template:
            return HttpResponse(json.dumps({'code': -1, 'msg': '模板不存在'}))
        template.is_in_use = 0
        for module_id in template.required_modules.split(','):
            module = ProfileModule.objects.get(id=int(module_id))
            module.use_times -= 1
            if module.is_in_use == 1 and module.use_times > 0:
                # module.is_in_use = 0
                for field_dict in json.loads(module.required_fields):
                    field = ProfileField.objects.get(id=int(field_dict.get("field_id")))
                    field.use_times -= 1
                    if field.is_in_use == 1 and field.use_times > 0:
                        field.save()
                    elif field.is_in_use == 1 and field.use_times == 0:
                        field.is_in_use = 0
                        field.save()
                module.save()
            elif module.is_in_use == 1 and module.use_times == 0:
                module.is_in_use = 0
                module.save()
                for field_dict in json.loads(module.required_fields):
                    field = ProfileField.objects.get(id=int(field_dict.get("field_id")))
                    field.use_times -= 1
                    if field.is_in_use == 1 and field.use_times > 0:
                        field.save()
                    elif field.is_in_use == 1 and field.use_times == 0:
                        field.is_in_use = 0
                        field.save()
        template.save()
        return HttpResponse(json.dumps({'code': 0, 'msg': "", "template_id":template.id, "is_in_use":0}))


def render_template(request):
    if request.method == 'GET':
        template_id = request.GET.get('template_id')
        platform = get_employee_platform(request)[0].name
        module_set = []
        template_obj = ProfileFlow.objects.get(id=template_id, platform = platform)
        if not template_obj:
            return HttpResponse(json.dumps({'code': -1, 'msg': '模板不存在'}))
        modules = template_obj.required_modules
        sorted_modules = modules.split(',')
        for index, module_id in enumerate(sorted_modules):
            field_set = []
            module = ProfileModule.objects.get(id=module_id)
            fields_set = json.loads(module.required_fields)
            for field in fields_set:
                field_obj = ProfileField.objects.get(id=field.get('field_id'))
                field_set.append({'int32_is_must':field.get('is_must'), 'string_desc':field_obj.show_name, 'string_json':field_obj.reserve, 'string_name':field_obj.name, 'string_type':field_obj.type, 'string_user_value':''})
            module_set.append({'int32_is_must':1, 'int32_is_submitted':0, 'int32_level':0, 'int32_module_id':module.id, 'string_layout':'default', 'string_module_name':module.show_name, 'field_set':field_set})
        result = {'int32_apply_status':0, 'int32_user_id':0, 'strategy_info':{}, 'strategy_set':[], 'string_commodity_info':'', 'string_salesman_code':'', 'module_set':module_set}
        return HttpResponse(json.dumps({'code':0, 'msg':'', 'logic_rsp':result}))




@csrf_exempt
@page_permission(check_employee)
def add_workflow(request):
    if request.method == "POST":
        # post_data = json.loads(request.body)
        post_data = request.POST

        name = post_data.get("name")
        desc = post_data.get("desc")
        belong = post_data.get("belong")
        product = post_data.get('product')
        platform = get_employee_platform(request)[0].name

        if name:
            workflow = WorkFlow()
            workflow.name = name
            workflow.description = desc
            workflow.belong_product = product
            workflow.platform = platform
            if belong:
                workflow.belong = belong
            workflow.save()

            init_workstatus = WorkStatus()
            init_workstatus.name = '待审核'
            init_workstatus.status_code = '0'
            init_workstatus.is_start = 1
            init_workstatus.is_inner = 2
            init_workstatus.workflow = workflow
            init_workstatus.belong_product = product
            init_workstatus.platform = platform
            init_workstatus.save()

            init_workstatus1 = WorkStatus()
            init_workstatus1.name = '拒绝'
            init_workstatus1.status_code = 'n'
            init_workstatus1.is_end = 1
            init_workstatus1.is_inner = 2
            init_workstatus1.workflow = workflow
            init_workstatus1.belong_product = product
            init_workstatus1.platform = platform
            init_workstatus1.save()

            init_workstatus2 = WorkStatus()
            init_workstatus2.name = '通过'
            init_workstatus2.status_code = 'y'
            init_workstatus2.is_end = 1
            init_workstatus2.is_inner = 2
            init_workstatus2.workflow = workflow
            init_workstatus2.belong_product = product
            init_workstatus2.platform = platform
            init_workstatus2.save()

            return HttpResponse(json.dumps({'code': 0, 'msg': "", "workflow_id":workflow.id, "is_in_use":0, "is_delete":0}))
        else:
            return HttpResponse(json.dumps({'code': -1, 'msg': "信息填写不完整", "workflow_id":"", "is_in_use":0, "is_delete":0}))



@csrf_exempt
@page_permission(check_employee)
def delete_workflow(request):
    if request.method == "POST":
        workflow_id = request.POST.get("workflow_id")
        platform = get_employee_platform(request)[0].name
        workflow = WorkFlow.objects.get(id=workflow_id, platform = platform)
        if not workflow:
            return HttpResponse(json.dumps({'code': -1, 'msg': '流程不存在'}))

        # if workflow.apply_set.all().count() == workflow.apply_set.filter(status='y').count():
        if workflow.is_in_use == 0 and workflow.is_delete == 0 and workflow.is_used == 0:
            workflow.is_delete = 1
            workflow.save()
            return HttpResponse(json.dumps({'code': 0, 'msg': "", "workflow_id":workflow.id, "is_in_use":0, "is_delete":0}))
        elif workflow.is_in_use == 1 or workflow.is_delete == 1 or workflow.is_used == 1:
            return HttpResponse(json.dumps({'code': -1, 'msg': "该流程正在使用或已使用过，不能删除。", "workflow_id":workflow.id, "is_in_use":workflow.is_in_use, "is_delete":workflow.is_delete}))
        # elif workflow.apply_set.all().count() > workflow.apply_set.filter(status='y').count():
                # return HttpResponse(json.dumps({'code': -1, 'msg': "还有订单正在使用该流程，不能删除。", "workflow_id":workflow.id, "is_in_use":workflow.is_in_use, "is_delete":workflow.is_delete}))



@csrf_exempt
@page_permission(check_employee)
def update_workflow(request):     #仅能更新工作流的名称及描述
    if request.method == "POST":
        post_data = request.POST
        workflow_id = post_data.get("workflow_id")
        name = post_data.get("name")
        desc = post_data.get("desc")
        platform = get_employee_platform(request)[0].name
        product = post_data.get('product')

        workflow = WorkFlow.objects.get(id=workflow_id, platform = platform)
        if not workflow:
            return HttpResponse(json.dumps({'code': -1, 'msg': '流程不存在'}))
        if workflow.is_in_use == 0 and workflow.is_delete == 0 and workflow.is_used == 0:
            if name:
                workflow.name = name
                workflow.description = desc
                if product:
                    workflow.belong_product = product
                workflow.save()
                return HttpResponse(json.dumps({'code': 0, 'msg': "", "workflow_id":workflow.id, "name":workflow.name, "desc":workflow.description, "belong":workflow.belong, "is_in_use":0}))
            else:
                return HttpResponse(json.dumps({'code': -1, 'msg': "请完善信息", "workflow_id":workflow.id, "name":workflow.name, "desc":workflow.description, "belong":workflow.belong, "is_in_use":0}))
        elif workflow.is_in_use == 1 or workflow.is_delete == 1 or workflow.is_used == 1:
            return HttpResponse(json.dumps({'code': -1, 'msg': "该流程正在使用或已经使用过，不能更新流程信息", "workflow_id":workflow.id, "name":workflow.name, "desc":workflow.description, "belong":workflow.belong, "is_in_use":workflow.is_in_use}))


@csrf_exempt
# @page_permission(check_employee)
def get_workflow(request):
    if request.method == "GET":
        platform = get_employee_platform(request).values_list('name', flat = True)
        workflows_id = request.GET.get("workflows_id")
        result_list = []
        if workflows_id:
            workflows_id = map(int, workflows_id.split(','))
            workflows = WorkFlow.objects.filter(id__in = workflows_id, platform__in = platform)
            for workflow in workflows:
                product = Product.objects.get(name = workflow.belong_product, platform = workflow.platform)
                result_list.append({"workflow_id":workflow.id, 
                                    "name":workflow.name, 
                                    "desc":workflow.description, 
                                    "belong":workflow.belong, 
                                    "is_in_use":workflow.is_in_use, 
                                    "is_delete":workflow.is_delete,
                                    'product': workflow.belong_product,
                                    'product_name': product.show_name})
        else:
            workflows = WorkFlow.objects.filter(is_delete=0, platform__in = platform)
            if workflows.count() > 0:
                for workflow in workflows:
                    product = Product.objects.get(name = workflow.belong_product, platform = workflow.platform)
                    result_list.append({"workflow_id":workflow.id, 
                                        "name":workflow.name, 
                                        "desc":workflow.description, 
                                        "belong":workflow.belong, 
                                        "is_in_use":workflow.is_in_use, 
                                        "is_delete":workflow.is_delete,
                                        'product': workflow.belong_product,
                                        'product_name': product.show_name})
            elif workflows.count() == 0:
                return HttpResponse(json.dumps({"code":0, "msg":"", "workflows":''}))
        return HttpResponse(json.dumps({"code":0, "msg":"", "workflows":result_list}))


def _stop_using_workflow(workflow=None):
    if not workflow:
        return

    status_flow_list = StatusFlow.objects.filter(flow_id=workflow.id)
    for _status in status_flow_list:
        if _status.template_id:
            template_info = json.loads(_status.template_id)
            if not template_info['id']:
                continue
            template = ProfileFlow.objects.get(id=template_info['id'])
            template.use_times -= 1
            if template.use_times <= 0:
                template.is_in_use = 0
            template.save()
            for module_id in template.required_modules.split(','):
                module = ProfileModule.objects.get(id=int(module_id))
                module.use_times -= 1
                if module.is_in_use == 1 and module.use_times > 0:
                    for field_dict in json.loads(module.required_fields):
                        field = ProfileField.objects.get(id=int(field_dict.get('field_id')))
                        field.use_times -= 1
                        if field.is_in_use == 1 and field.use_times > 0:
                            field.save()
                        elif field.is_in_use == 1 and field.use_times == 0: 
                            field.is_in_use = 0
                            field.save()
                    module.save()
                elif module.is_in_use == 1 and module.use_times == 0:
                    module.is_in_use = 0
                    module.save()
                    for field_dict in json.loads(module.required_fields):
                        field = ProfileField.objects.get(id=int(field_dict.get('field_id')))
                        field.use_times -= 1
                        if field.is_in_use == 1 and field.use_times > 0:
                            field.save()
                        elif field.is_in_use == 1 and field.use_times == 0:
                            field.is_in_use = 0
                            field.save()
    return True


@csrf_exempt
@page_permission(check_employee)
def use_workflow(request):
    if request.method == 'POST':
        workflow_id = request.POST.get('workflow_id')
        platform = get_employee_platform(request)[0].name
        workflow = WorkFlow.objects.get(id=workflow_id, platform = platform)
        using_workflow_set = WorkFlow.objects.filter(is_in_use=1, platform = platform, belong_product = workflow.belong_product)
        if using_workflow_set.count() > 0:
            using_workflow = using_workflow_set[0]
            if using_workflow.id != workflow_id and workflow.is_delete == 0:
                try:
                    _stop_using_workflow(using_workflow)
                except Exception, e:
                    print(e)
                using_workflow.is_in_use = 0
                using_workflow.save()
                workflow.is_in_use = 1
                workflow.save()
                status_flow_list = StatusFlow.objects.filter(flow_id = workflow.id)
                for s in status_flow_list:
                    if not s.template_id:
                        continue
                    template_info = json.loads(s.template_id)
                    print 'template_info', template_info
                    if not template_info['id']:
                        continue
                    template = ProfileFlow.objects.get(pk = template_info['id'])
                    template.is_in_use = 1
                    template.use_times += 1
                    _count_times(template)
                    template.save()
                return HttpResponse(json.dumps({"code":0, "msg":"", "workflow_id":workflow.id, 'is_in_use':workflow.is_in_use}))
            elif using_workflow.id == workflow_id:
                return HttpResponse(json.dumps({"code":-1, "msg":"流程已在使用中。", "workflow_id":'', 'is_in_use':''}))
            elif workflow.is_delete == 1:
                return HttpResponse(json.dumps({"code":-1, "msg":"流程已删除，不能启用。", "workflow_id":'', 'is_in_use':''}))
        elif using_workflow_set.count() == 0:
            workflow.is_in_use = 1
            workflow.is_used = 1
            workflow.save()
            status_flow_list = StatusFlow.objects.filter(flow_id = workflow.id)
            for s in status_flow_list:
                if not s.template_id:
                    continue
                template_info = json.loads(s.template_id)
                if not template_info['id']:
                    continue
                template = ProfileFlow.objects.get(pk = template_info['id'])
                template.is_in_use = 1
                template.use_times += 1
                _count_times(template)
                template.save()
            return HttpResponse(json.dumps({"code":0, "msg":"", "workflow_id":workflow.id, 'is_in_use':workflow.is_in_use}))


@csrf_exempt
@page_permission(check_employee)
def abandon_workflow(request):
    if request.method == 'POST':
        workflow_id = request.POST.get('workflow_id')
        platform = get_employee_platform(request)[0].name
        workflow = WorkFlow.objects.get(id=workflow_id, platform = platform)
        if not workflow:
            return HttpResponse(json.dumps({'code': -1, 'msg': '流程不存在'}))

        workflow.is_in_use = 0
        workflow.save()

        status_flow_list = StatusFlow.objects.filter(flow_id = workflow.id)
        for s in status_flow_list:
            if not s.template_id:
                continue
            template_info = json.loads(s.template_id)
            template = ProfileFlow.objects.get(id = template_info['id'])
            template.use_times -= 1
            if template.use_times <= 0:
                template.is_in_use = 0
            for module_id in template.required_modules.split(','):
                module = ProfileModule.objects.get(id=int(module_id))
                module.use_times -= 1
                if module.is_in_use == 1 and module.use_times > 0:
                    module.is_in_use = 0
                    for field_dict in json.loads(module.required_fields):
                        field = ProfileField.objects.get(id=int(field_dict.get("field_id")))
                        field.use_times -= 1
                        if field.is_in_use == 1 and field.use_times > 0:
                            field.save()
                        elif field.is_in_use == 1 and field.use_times == 0:
                            field.is_in_use = 0
                            field.save()
                    module.save()
                elif module.is_in_use == 1 and module.use_times == 0:
                    module.is_in_use = 0
                    module.save()
                    for field_dict in json.loads(module.required_fields):
                        field = ProfileField.objects.get(id=int(field_dict.get("field_id")))
                        field.use_times -= 1
                        if field.is_in_use == 1 and field.use_times > 0:
                            field.save()
                        elif field.is_in_use == 1 and field.use_times == 0:
                            field.is_in_use = 0
                            field.save()
            template.save()
        return HttpResponse(json.dumps({"code":0, "msg":"", "workflow_id":workflow.id, 'is_in_use':workflow.is_in_use}))


@csrf_exempt
@page_permission(check_employee)
def add_workstatus(request):
    if request.method ==  "POST":
        post_data = request.POST
        workflow_id = post_data.get('workflow_id')
        name = post_data.get('name')
        other_name = post_data.get('other_name')
        desc = post_data.get('desc')
        status_code = post_data.get('status_code')
        platform = get_employee_platform(request)[0].name

        workflow = WorkFlow.objects.get(id=workflow_id, platform = platform)
        if not workflow:
            return HttpResponse(json.dumps({'code': -1, 'msg': '流程不存在'}))

        if workflow.is_in_use == 1 or workflow.is_delete == 1:
            return HttpResponse(json.dumps({"code":-1, "msg":'工作流正在使用，不能添加新状态'}))
        elif workflow.is_in_use == 0 and workflow.is_delete == 0:
            if workflow.apply_set.all().count() == workflow.apply_set.filter(status='y').count():
                if workflow.is_used == 0:
                    workstatus = WorkStatus()
                    workstatus.name = name
                    workstatus.other_name = other_name
                    workstatus.description = desc
                    workstatus.status_code = status_code
                    workstatus.workflow = workflow
                    workstatus.platform = platform
                    workstatus.save()
                    return HttpResponse(json.dumps({"code":0, "msg":"", "workstatus_id":workstatus.id, "name":workstatus.name, "other_name":workstatus.other_name, "desc":workstatus.description, "status_code":workstatus.status_code}))
                elif workflow.is_used == 1:
                    pass
            elif workflow.apply_set.all().count() > workflow.apply_set.filter(status='y').count():
                return HttpResponse(json.dumps({"code":-1, "msg":'尚有订单正在使用该工作流，暂时不能添加新状态。'}))


@csrf_exempt
@page_permission(check_employee)
def delete_workstatus(request):
    if request.method == "POST":
        workstatus_id = request.POST.get('workstatus_id')
        platform = get_employee_platform(request)[0].name

        workstatus = WorkStatus.objects.get(id=workstatus_id, platform = platform)
        if not workstatus:
            return HttpResponse(json.dumps({'code': -1, 'msg': '该状态不存在'}))
        workflow = workstatus.workflow
        if workflow.is_used == 0:
            workstatus.is_delete = 1
            workstatus.save()
            return HttpResponse(json.dumps({"code":0, "msg":''}))
        elif workflow.is_used == 1:
            return HttpResponse(json.dumps({"code":-1, "msg":'该流程已使用过，不能删除该状态。'}))


@csrf_exempt
@page_permission(check_employee)
def update_workstatus(request):
    if request.method == "POST":
        post_data = request.POST
        workflow_id = post_data.get('workflow_id')
        workstatus_id = post_data.get('workstatus_id')
        other_name = post_data.get('other_name')
        desc = post_data.get('desc')
        platform = get_employee_platform(request)[0].name

        workflow = WorkFlow.objects.get(id=workflow_id, platform = platform)
        if not workflow:
            return HttpResponse(json.dumps({'code': -1, 'msg': '流程不存在'}))
        if workflow.is_used == 0:
            workstatus = WorkStatus.objects.get(id=workstatus_id)
            workstatus.other_name = other_name
            workstatus.description = desc
            workstatus.save()
            return HttpResponse(json.dumps({"code":0, "msg":'', 'id':workstatus.id, 'name':workstatus.name, 'other_name':workstatus.other_name, 'desc':workstatus.description, 'status_code':workstatus.status_code}))
        elif workflow.is_used == 1 or workflow.is_in_use == 1:
            return HttpResponse(json.dumps({"code":-1, "msg":'流程正在使用或已使用过，不能对流程状态进行修改。', 'workstatus_id':workstatus.id, 'name':workstatus.name, 'other_name':workstatus.other_name, 'desc':workstatus.description, 'status_code':workstatus.status_code}))


@csrf_exempt
@page_permission(check_employee)
def get_workstatus(request):
    if request.method == 'GET':
        workflow_id = request.GET.get('workflow_id')
        platform = get_employee_platform(request).values_list('name', flat = True)
        result_list = []
        if workflow_id:
            workflow = WorkFlow.objects.get(id=workflow_id, platform__in = platform)
            workstatuses = workflow.workstatus_set.filter(is_delete=0)
            for workstatus in workstatuses:
                result_list.append({"id":workstatus.id, 
                                    "name":workstatus.name, 
                                    "other_name":workstatus.other_name, 
                                    "desc":workstatus.description, 
                                    "status_code":workstatus.status_code, 
                                    "is_start":workstatus.is_start, 
                                    "is_end":workstatus.is_end, 
                                    "is_inner":workstatus.is_inner,
                                    "product": workflow.belong_product})
        else:
            workstatuses = WorkStatus.objects.filter(is_inner=1, platform__in = platform)
            for workstatus in workstatuses:
                result_list.append({"id":workstatus.id, 
                                    "name":workstatus.name, 
                                    "other_name":workstatus.other_name, 
                                    "desc":workstatus.description, 
                                    "status_code":workstatus.status_code, 
                                    "is_start":workstatus.is_start, 
                                    "is_end":workstatus.is_end, 
                                    "is_inner":workstatus.is_inner})
        return HttpResponse(json.dumps({"code":0, "msg":"", "workstatuses":result_list}))

@csrf_exempt
@page_permission(check_employee)
def add_statusflow(request):
    if request.method == 'POST':
        json_string = request.POST.get('data')
        json_data = json.loads(json_string)
        workflow_id = json_data.get('workflow_id')
        platform = get_employee_platform(request)[0].name
        workflow_obj = WorkFlow.objects.get(id=workflow_id, platform = platform)
        if not workflow_obj:
            return HttpResponse(json.dumps({'code': -1, 'msg': '流程不存在'}))
        if workflow_obj.is_used == 1:
            return HttpResponse(json.dumps({'code':-1, 'msg':'流程已使用过，不能在更改流程设置。'}))
        StatusFlow.objects.filter(flow_id=workflow_id).delete()
        workstatuses_set = json_data.get('workstatuses_id')

        for workstatus in workstatuses_set:
            statusflow = StatusFlow()
            statusflow.flow_id = workflow_id
            statusflow.status_id = workstatus.get('current')
            statusflow.next_status_id = workstatus.get('next')
            statusflow.template_id = json.dumps(workstatus.get('template_id'))
            # flow = workstatus.get('template_id')
            # pf = ProfileFlow.objects.get(pk=flow.get('id'))
            # pf.is_in_use = 1
            # pf.save()
            statusflow.save()
        return HttpResponse(json.dumps({"code":0, "msg":'', }))


@csrf_exempt
@page_permission(check_employee)
def get_statusflow(request):
    if request.method == 'GET':
        workflow_id = request.GET.get('workflow_id')
        statusflow_set = StatusFlow.objects.filter(flow_id=workflow_id)
        result = []
        for statusflow in statusflow_set:
            result.append({'current':statusflow.status_id, 'next':statusflow.next_status_id, 'template_id':json.loads(statusflow.template_id)})
        return HttpResponse(json.dumps({'code':0, 'msg':'', 'workstatuses_id':result}))

def create_experiment(request):
    if request.method == 'POST':
        percentage = int(request.POST.get('percentage'))
        experiment_name = request.POST.get('experiment_name')
        new_experiment = ExperimentPercentage(percentage = percentage, experiment_name = experiment_name)
        new_experiment.save()
        experiment_count = int(request.POST.get('experiment_count'))
        for i in range(experiment_count):
            filter_count = int(request.POST.get('filter_count_%d' % i))
            filter = []
            for j in range(filter_count):
                tmp = {}
                field_name = request.POST.get('field_name_%d_%d' % (i, j))
                filter_type = request.POST.get('type_%d_%d' % (i, j))
                tmp['name'] = field_name
                tpm['type'] = filter_type
                if filter_type == 'equal':
                    value = request.POST.get('value_%d_%d' % (i, j))
                    tmp['value'] = value
                elif filter_type == 'range':
                    max = int(request.POST.get('max_%d_%d' % (i, j)))
                    min = int(request.POST.get('min_%d_%d' % (i, j)))
                    tmp['max_value'] = max
                    tmp['min_value'] = min
                filter.append(tmp)
            new_filter = ReviewExperiment(filter = json.dumps(filter), model_id = request.POST.get('model_id_%d' % i),
                                         belong = new_experiment)
            new_filter.save()
        return HttpResponse(json.dumps({'result': 'ok', 'exp_id': new_experiment.id}))

def delete_experiment(request):
    if request.method == 'GET':
        experiment_id = int(request.GET.get('experiment_id'))
        experiment = ExperimentPercentage.objects.get(pk = experiment_id)
        if experiment:
            experiment.delete()
        return HttpResponse(json.dumps({'result': 'ok'}))

def add_model_to_experiment(request):
    if request.method == 'POST':
        experiment_id = request.POST.get('experiment_id')
        experiment = ExperimentPercentage.objects.get(pk = experiment_id)
        if not experiment:
            Log().error('experiment {0} is not exist'.format(experiment_id))
            return HttpResponse(json.dumps({'error': u'实验不存在'}))
        filter_count = int(request.POST.get('filter_count'))
        filter = []
        for i in range(filter_count):
            tmp = {}
            field_name = request.POST.get('field_name_%d' % i)
            filter_type = request.POST.get('type_%d' % i)
            tmp['name'] = field_name
            tmp['type'] = filter_type
            if filter_type == 'equal':
                value = request.POST.get('value_%d' % i)
                tmp['value'] = value
            elif filter_type == 'range':
                max = int(request.POST.get('max_%d' % i))
                min = int(request.POST.get('min_%d' % i))
                tmp['max_value'] = max
                tmp['min_value'] = min
            filter.append(tmp)
        new_filter = ReviewExperiment(filter = json.dumps(filter), model_id = request.POST.get('model_id'),
                                     belong = experiment)
        new_filter.save()
        return HttpResponse(json.dumps({'result': 'ok', 'filter_id': new_filter.id}))

def del_model_from_experiment(request):
    if request.method == 'GET':
        filter_id = request.GET.get('filter_id')
        filter = ReviewExperiment(pk = filter_id)
        if filter:
            filter.delete()
        return HttpResponse(json.dumps({'result': 'ok'}))

def modify_filter(request):
    if request.method == 'POST':
        filter_id = request.POST.get('filter_id')
        old_filter = ReviewExperiment.objects.get(pk = filter_id)
        if not old_filter:
            Log().error('modify_filter failed, filter {0} is not exist'.format(filter_id))
            return HttpResponse(json.dumps({'error': u'过滤器不存在'}))
        filter_count = int(request.POST.get('filter_count'))
        filter = []
        for i in range(filter_count):
            tmp = {}
            field_name = request.POST.get('field_name_%d' % i)
            filter_type = request.POST.get('type_%d' % i)
            tmp['name'] = field_name
            tmp['type'] = filter_type
            if filter_type == 'equal':
                value = request.POST.get('value_%d' % i)
                tmp['value'] = value
            elif filter_type == 'range':
                max = int(request.POST.get('max_%d' % i))
                min = int(request.POST.get('min_%d' % i))
                tmp['max_value'] = max
                tmp['min_value'] = min
            filter.append(tmp)
        old_filter.filter = json.dumps(filter)
        old_filter.model_id = request.POST.get('model_id')
        old_filter.save()
        return HttpResponse(json.dumps({'result': 'ok'}))

@csrf_exempt
@page_permission(check_employee)
def call_pass_line(request):
    if request.method == 'POST':
        call_type = request.POST.get('type')
        pass_line = int(request.POST.get('pass_line'))
        if not redis_client.set(CALL_PASS_LINE_KEY % call_type, pass_line):
            return HttpResponse(json.dumps({'code': -1, 'msg': u'服务器错误，请稍后重试'}))
        return HttpResponse(json.dumps({'code': 0}))
    else:
        call_types = request.GET.get('type').split(',')
        result = {}
        for call_type in call_types:
            pass_line = redis_client.get(CALL_PASS_LINE_KEY % call_type)
            if not pass_line:
                result[call_type] = 100
            else:
                result[call_type] = int(pass_line)
        return HttpResponse(json.dumps({'code': 0, 'pass_line': result}))

def get_product_list(request):
    if request.method == 'GET':
        platform = get_employee_platform(request)[0].name
        product_list = Product.objects.filter(platform = platform, is_in_use = 1)
        result = []
        for product in product_list:
            result.append({'name': product.name,
                           'show_name': product.show_name})
        return HttpResponse(json.dumps({'code': 0, 'product': result}))

def get_modules_from_system_name(request):
    if request.method == 'GET':
        key = request.GET.get("system_name", None)
        if not key:
            return {"code": -2, "msg": "缺少参数"}
        platform = get_employee_platform(request).values_list('name', flat = True)
        product = request.GET.get('product', '')
        if product:
            profile_flow = ProfileFlow.objects.filter(belong_system=key, is_delete = 0, platform__in = platform, belong_product = product)
        else:
            profile_flow = ProfileFlow.objects.filter(belong_system=key, is_delete = 0, platform__in = platform)
        flow_list = []
        for row in profile_flow:
            data = copy.deepcopy(row.__dict__)
            if "_state" in data:
                data.pop("_state")
            data.pop('belong_product')
            print row.belong_product
            platform_db = Platform.objects.get(name = row.platform)
            print row, data
            product_db = Product.objects.get(name = row.belong_product, platform = row.platform)
            data['platform_name'] = platform_db.show_name
            data['product_name'] = product_db.show_name
            data['product'] = row.belong_product
            flow_list.append(data)
        return HttpResponse(json.dumps({'code': 0, 'msg': "", "data": flow_list}))





