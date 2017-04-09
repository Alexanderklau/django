#!/usr/bin/env python
# coding=utf-8

from django.db.models import Q
from business_manager.order.apply_models import Apply
from business_manager.order.models import *
from business_manager.util.tkdate import *
from business_manager.util.data_provider import DataProvider
from business_manager.python_common.log_client import CommonLog as Log
from business_manager.employee.models import get_employee_platform

class OrderDataProvider(DataProvider):
    def object_filter(self, request):
        stime = get_today()
        etime = get_tomorrow()
        timerange =request.GET.get("time")
        if timerange == "today" :
            stime = get_today()
            etime = get_tomorrow()
        elif timerange == "yestoday" :
            stime = get_yestoday()
            etime = get_today()
        elif timerange == "toweek" :
            stime = get_first_day_of_week()
            etime = get_tomorrow()
        elif timerange == "tomonth" :
            stime = get_first_day_of_month()
            etime = get_tomorrow()
        else:
            stime = request.GET.get("stime")
            etime = request.GET.get("etime")
        user_platform = get_employee_platform(request)
        platform_query = Q()
        if len(user_platform) > 1:
            platform_param = request.GET.get('platform', '')
            if platform_param:
                platform_query = Q(platform = platform_param)
            else:
                platform_query = Q(platform__in = user_platform.values_list('name'))
        else:
            platform_query = Q(platform = user_platform[0].name)
        product_query = Q()
        product = request.GET.get('product', '')
        if product:
            product_query = Q(product = product)

        print stime, etime
        try:
            order_list = Apply.objects.filter(Q(create_at__lt = etime, create_at__gt = stime, type = '0') & platform_query & product_query)
            return order_list
        except Exception,e:
            print 'filter failed:', e
            Log().error('OrderDataProvider filter failed, err:{0}'.format(e))
            return None

    def get_columns(self):
        return [u"订单ID", u"用户名", u"创建时间", u"订单状态"]

    def get_query(self):
        return ["id__iexact", "create_by__name__icontains", "create_by__phone_no__icontains"]

    def fill_data(self, query_set):
        data_set = []
        for result in query_set.values():
            apply = Apply.objects.get(pk = result["id"])
            user = apply.create_by
            chsi = Chsi.objects.filter(user=user)
            data = [apply.id,
                    user.name,
                    apply.create_at.strftime("%Y-%m-%d %H:%M:%S") if apply.create_at else "",
                    apply.get_status_display()]
            data_set.append(data)
        print 'data_set:', data_set
        return data_set

def get_all_apply_datatable(request):
    print request
    return OrderDataProvider().get_datatable(request)

def get_order_columns():
    return OrderDataProvider().get_columns()

