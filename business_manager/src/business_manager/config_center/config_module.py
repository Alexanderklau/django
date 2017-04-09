#!/usr/bin/env python
# coding=utf-8

from business_manager.config_center.models import ProfileFlow, Product
from business_manager.employee.models import Platform

def get_modules_from_system_name(data_dict, platform):
    print data_dict, platform
    key = data_dict.get("system_name", None)
    print key
    if not key or not platform:
        return {"code": -2, "msg": "缺少参数"}
    profile_flow = ProfileFlow.objects.filter(belong_system=key, is_delete = 0, platform__in = platform)
    flow_list = []
    for row in profile_flow:
        data = row.__dict__
        if "_state" in data:
            data.pop("_state")
        data.pop('belong_product')
        platform_db = Platform.objects.get(name = row.platform)
        print row, data
        product_db = Product.objects.get(name = row.belong_product, platform = row.platform)
        data['platform_name'] = platform_db.show_name
        data['product_name'] = product_db.show_name
        data['product'] = row.belong_product
        flow_list.append(data)
    return {"data": flow_list}
