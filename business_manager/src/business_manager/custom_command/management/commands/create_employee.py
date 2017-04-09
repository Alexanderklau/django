#-*- coding: utf-8 -*-
"""
创建 催收用户组.
将 review_employee 移动到 employee 并关联相关字段

"""

from django.core.management.base import BaseCommand, CommandError
from django.db import models
#from placeholders import *
import os
import httplib
import urllib2
import urllib

from business_manager.order.apply_models import Apply, ExtraApply, CheckApply
from business_manager.review.models import Review,  ReviewRecord, CollectionRecord, BankStatement
from business_manager.collection.models import *
from business_manager.review import message_client, bank_client, risk_client, redis_client

from business_manager.employee.models import *


def create_employee_group():
    # collection_groups_name = '分配订单,查看逾期订单,逾期订单催收,催收BI查看(个人),催收BI查看(主管),数据导入,模板配置'.split(',')
    collection_manager_perms = u'分配订单,查看逾期订单,逾期订单催收,催收BI查看(个人),催收BI查看(主管)'.split(',')
    collection_perms = u'查看逾期订单,逾期订单催收,催收BI查看(个人)'.split(',')
    collector = u'催收M1,催收M2,催收M3,催收M4,催收M5,催收M5以上'.split(',')

    if not EmployeeGroup.objects.filter(group_name = u'催收主管'):
        group = EmployeeGroup(group_name = u'催收主管', is_editable = 1)
        group.save()

        permission_list = PermissionSet.objects.filter(name__in=collection_manager_perms)
        for p in permission_list:
            group.permissions.add(p)

    for _cname in collector:
        if not EmployeeGroup.objects.filter(group_name = _cname):

            cgroup = EmployeeGroup(group_name=_cname, is_editable = 1)
            cgroup.save()
            permission_list = PermissionSet.objects.filter(name__in=collection_perms)
            for p in permission_list:
                cgroup.permissions.add(p)

            cgroup.save()





class Command(BaseCommand):
    def handle(self, *args, **options):
        create_employee_group()

        review_employee_sql = 'select * from review_employee'
        review_employee = Employee.objects.raw(review_employee_sql)
        for re in review_employee:
            print re
            print re.id, re.user, re.username, re.phone_no, re.work_dispatch, re.post, re.phone
            # if re.post not in ['cm', 'cs']:
                # continue
            post = re.post
            group_name = ''
            if Employee.objects.filter(id=re.id):
                continue

            if post == 'cm':
                group_name = '催收主管'
            if post == 'cs':
                work_dispatch_dic = {
                    10: 'cs_m1',
                    11: 'cs_m2',
                    12: 'cs_m3',
                    13: 'cs_m4',
                }
                group_dic= {
                    10: '催收M1',
                    11: '催收M2',
                    12: '催收M3',
                    13: '催收M4',
                }
                post = work_dispatch_dic.get(re.work_dispatch)
                group_name = group_dic.get(re.work_dispatch)
            # if not post:
                # continue

            print '-----print-'
            data = dict(
                id=re.id,
                user=re.user,
                username=re.username,
                mobile=re.phone,
                telephone=re.phone_no,
                post=post,
                # group_list='',
                leader=0,
                id_no='',
            )
            print data
            employee = Employee(**data)
            employee.save()
            eg = EmployeeGroup.objects.filter(group_name=group_name).first()
            if eg:
                print eg
                print type(eg)
                print eg.id
                employee.group_list.add(eg)
            employee.save()

    post = models.CharField(blank = True, null = True, max_length = 16, choices = post_t)
    group_list = models.ManyToManyField(EmployeeGroup)
    leader = models.IntegerField(help_text = u'直属领导', default = 0)
    id_no = models.CharField(help_text = u'身份证号码', max_length = 32)



