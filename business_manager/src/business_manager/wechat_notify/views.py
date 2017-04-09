# -*- coding:utf-8 -*-
from django.http import HttpResponse
from django.shortcuts import render
from django.db.models import Sum, Count
from business_manager.util.common_response import ImportResponse

from business_manager.order.apply_models import Apply
from business_manager.employee.models import Employee, get_collector_employee_group
# Create your views here.

DAYS_NOTIFY = (u"3天后将流失的客户：{}户，总还款金额{}元；"
               u"2天后将流失的客户：{}户，总还款金额{}元；"
               u"1天后将流失的客户：{}户，总还款金额{}元。")


M1_LIMIT = 30
M2_LIMIT = 60
M3_LIMIT = 90
M4_LIMIT = 120
M5_LIMIT = 150
ABOVE_M5_LIMIT = 180

APPLY_STATUS = {
    u'催收M1': M1_LIMIT,
    u'催收M2': M2_LIMIT,
    u'催收M3': M3_LIMIT,
    u'催收M4': M4_LIMIT,
    u'催收M5': M4_LIMIT,
    u'催收M5以上': ABOVE_M5_LIMIT,
}


COLLECT_STATUS = (Apply.COLLECTION,
                  Apply.PROCESSING)


def wechat_get_recently_applys(username):
    # username = request.GET['username']
    employee = Employee.objects.filter(user__username=username.strip()).first()
    if not employee:
        return '没有该雇员。'
    employee_group = set(employee.group_list.distinct()) & set(get_collector_employee_group())
    if not employee_group:
        # not found collector group
        return '没找到该雇员的催收组。'
    group = employee_group.pop()
    print(group.group_name)
    overdue_days = APPLY_STATUS.get(group.group_name, 3)
    print(overdue_days)
    transfer_one = Apply.objects.filter(employee=employee,
                                        overdue_days=overdue_days,
                                        status__in=COLLECT_STATUS).aggregate(Sum('rest_repay_money'), Count('id'))
    transfer_two = Apply.objects.filter(employee=employee,
                                        overdue_days=overdue_days - 1,
                                        status__in=COLLECT_STATUS).aggregate(Sum('rest_repay_money'), Count('id'))
    transfer_three = Apply.objects.filter(employee=employee,
                                          overdue_days=overdue_days - 2,
                                          status__in=COLLECT_STATUS).aggregate(Sum('rest_repay_money'), Count('id'))
    print(transfer_three)
    msg = DAYS_NOTIFY.format(transfer_three['id__count'], convert_money(transfer_three['rest_repay_money__sum']),
                             transfer_two['id__count'], convert_money(transfer_two['rest_repay_money__sum']),
                             transfer_one['id__count'], convert_money(transfer_one['rest_repay_money__sum']), )
    return msg


def convert_money(money):
    if money:
        return round(money/100.0, 2)
    return '0'
