#!/usr/bin/env python
# coding=utf-8

from django.http import HttpResponse
import json
import config_module
from django.views.decorators.csrf import csrf_exempt
from business_manager.employee.models import get_employee_platform

@csrf_exempt
def dispatcher(request):
    which_func = "get_modules_from_system_name"
    request_data = request.POST if request.method == "POST" else request.GET
    print request_data
    platform = get_employee_platform(request).values_list('name', flat = True)
    try:
        func = getattr(config_module, which_func)
    except Exception, ex:
        return HttpResponse(
            json.dumps({
                "code"  : -4,
                "msg"   : "not found"
            })
        )
    res_dict            = func(request_data, platform)
    res_code            = res_dict.get("code", 0)
    res_dict["code"]    = res_code
    res_dict["msg"]     = res_dict.get("msg", "success" if res_code == 0 else "error")
    return HttpResponse(json.dumps(res_dict))
