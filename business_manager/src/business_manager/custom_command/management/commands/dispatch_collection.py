#!/usr/bin/env python
# coding=utf-8

from django.core.management.base import BaseCommand, CommandError
from django.db import models
from django.contrib.auth.models import User as AuthUser

import os, traceback, random
from datetime import datetime
import xlrd

from business_manager.python_common.log_client import CommonLog as Log
from business_manager.order.apply_models import Apply, CheckApply
from business_manager.review.models import Review, Employee, ReviewRecord, CollectionRecord
from business_manager.employee.models import Employee
# from business_manager.review.employee_models import get_dispatch_collector_list, get_employee
from business_manager.collection.models import RepaymentInfo

from business_manager.collection.services import collection_extra_data
from business_manager.collection.report import report_collection
from business_manager.collection.report import report_collection
from business_manager.order.models import User, BankCard


class Command(BaseCommand):
    def _read_id_from_excel(self, filename):
        fd = xlrd.open_workbook(filename)
        sh = fd.sheet_by_index(0)
        id_list = []
        print filename
        for i in range(sh.nrows):
            # for j in range(sh.ncols):
            value = sh.cell_value(i, 5)
            print value
            if not value:
                continue
            try:
                value = value.strip()
                print value
                id_list.append(str(value))
            except Exception as e:
                print 'error'
                print e
        return id_list

    def _dispatch_by_id(self, order_number_list, collector_name, channel='蓝领贷'):
        user = AuthUser.objects.get(username = collector_name)
        if not user:
            print 'user not exist'
            return
        collector = Employee.objects.filter(user = user)
        count = 0
        print user
        print collector
        errors = []
        for order_number in order_number_list:
            # 蓝领贷 分配
            try:
                print order_number
                lld = User.objects.get(id_no=order_number, channel=channel)
                repayment = RepaymentInfo.objects.filter(user_id=lld)
                if repayment.count() > 1:
                    print 'error'
                    raise ValueError('repayment count = %s' % repayment.count())

                print lld
                print repayment
                # continue
                # repayment = RepaymentInfo.objects.filter(order_number = order_number)
                if not repayment:
                    #print order_number
                    print 'error'
                    raise ValueError('repayment: %s is null ' % order_number)
                #print repayment
                apply = Apply.objects.filter(repayment = repayment[0])
                if not apply:
                    msg = 'apply not exist, order_number:', order_number
                    print msg
                    raise ValueError(msg)

                apply = apply[0]
                apply.employee = collector[0]
                apply.save()
                reviews = Review.objects.filter(order = apply).order_by("-id")
                if reviews.count() == 0:
                    count += 1
                    print order_number
                    collection_record_data = dict(
                        record_type=CollectionRecord.DISPATCH,
                        object_type=CollectionRecord.SELF,
                        collection_note=u"管理员 将客户分配给 %s" % collector[0].username,
                        create_by=collector[0],
                        apply=apply,
                    )
                    extra_data = collection_extra_data(apply)
                    collection_record_data.update(**extra_data)
                    CollectionRecord.objects.create(**collection_record_data)
                    report_collection(apply)

                    review = Review()
                    review.reviewer = collector[0]
                    review.create_at = datetime.now()
                    review.order = apply
                    if apply.status == '0':
                        review.review_res = 'i'
                        apply.status = 'i'
                        apply.employee = collector[0]
                        apply.save()
                    elif apply.status == '9':
                        review.review_res = 'y'
                    else:
                        review.review_res = 'i'
                    review.save()
            except Exception as e:
                print collector_name
                print e
                errors.append([collector_name, order_number, e])

        print 'error: list'
        print collector_name
        print errors
        print [_e[1] for _e in errors]
        print len(errors)
        print count

    def handle(self, *args, **options):
        try:
            Log().info('begin auto dispatch collection')
            print args
            collector_dict = {
                # 'hekebu': '/home/dengzhehao/apply_hekebu.xls',
                # 'hejie': '/home/dengzhehao/apply_hejie.xls',

                'zengyi': '/home/dengzhehao/apply_zengyi.xls',
                'daiqingfang': '/home/dengzhehao/apply_daiqingfang.xls',
                'huangweiwei': '/home/dengzhehao/apply_huangweiwei.xls',
                'jiangchunlin': '/home/dengzhehao/apply_jiangchunlin.xls',
                'liangshaobo': '/home/dengzhehao/apply_liangshaobo.xls',
                'liuying': '/home/dengzhehao/apply_liuying.xls',
                'machi': '/home/dengzhehao/apply_machi.xls',
                'renxiuyan': '/home/dengzhehao/apply_renxiuyan.xls',
                'wuchunyan': '/home/dengzhehao/apply_wuchunyan.xls',
            }
            for collector_name in collector_dict:
                order_number_list = self._read_id_from_excel(collector_dict[collector_name])
                order_number_list = order_number_list[1:]
                print order_number_list
                print collector_name, len(order_number_list)
                self._dispatch_by_id(order_number_list, collector_name)
        except Exception,e:
            Log().error('auto dispatch collection failed, err:{0}'.format(e))
            print 'error:', e
