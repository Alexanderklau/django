#!/usr/bin/env python
# coding=utf-8

from django.core.management.base import BaseCommand, CommandError
from django.db import models
from django.contrib.auth.models import User

import os, traceback, random
from datetime import datetime
import xlrd

from business_manager.python_common.log_client import CommonLog as Log
from business_manager.order.apply_models import Apply, CheckApply
from business_manager.review.models import Review, Employee, ReviewRecord, CollectionRecord
from business_manager.employee.models import get_dispatch_collector_list, get_employee
from business_manager.collection.models import RepaymentInfo, InstallmentDetailInfo

class Command(BaseCommand):

    def handle(self, *args, **options):
        try:
            Log().info('begin update apply')
            print args

            applys = Apply.objects.filter(type__in=['a', 'b', 'c', 'd', 'e', 'h', 'g'], status__in=['0', 'i', 'ci', 'd', 's1', 's2', 's3'])
            for a in applys:
                repayment = a.repayment
                print "repayment"
                print repayment.id
                installments = InstallmentDetailInfo.objects.filter(repayment=repayment.id)

                try:
                    overdue_days = max([ins.overdue_days for ins in installments if ins.repay_status == 2])
                    # # overdue_days = max([ins.overdue_days for ins in installments])
                except:
                    overdue_days = 0

                rest_repay_money = sum([ins.should_repay_amount for ins in installments if ins.repay_status == 2])
                # if not InstallmentDetailInfo.objects.filter(repayment=repayment.id, repay_status=2):
                    # done_installments = InstallmentDetailInfo.objects.filter(repayment=repayment.id, repay_status__in=[3, 8]).order_by("-real_repay_time")
                    # if done_installments:
                        # print "real_repay_amount"
                        # rest_repay_money = sum([ins.real_repay_amount for ins in done_installments if ins.real_repay_time == done_installments.first().real_repay_time])

                # real_installment = InstallmentDetailInfo.objects.filter(repayment=repayment.id).order_by("-real_repay_time").first()
                # real_repay_time = real_installment.real_repay_time

                a.rest_repay_money = rest_repay_money

                # collection_record_time = None
                # collection_type = [CollectionRecord.COLLECTION, CollectionRecord.MESSAGE, CollectionRecord.DISCOUNT]
                # collection_record = CollectionRecord.objects.filter(apply=a.id, record_type__in=collection_type).order_by("-create_at").first()
                # if collection_record:
                    # collection_record_time = collection_record.create_at

                if overdue_days:
                    a.overdue_days = overdue_days
                # if real_repay_time:
                    # a.real_repay_time = real_repay_time
                # if collection_record_time:
                    # a.collection_record_time = collection_record_time

                a.save()
                print "installment count"
                print installments.count()
                print rest_repay_money
            print 'aaa'
            print applys
            print applys.count()
        except Exception,e:
            print "error"
            print e
            Log().error('update apply failed, err:{0}'.format(e))






