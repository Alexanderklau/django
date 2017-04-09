#!/usr/bin/env python
# coding=utf-8

from django.core.management.base import BaseCommand, CommandError
from django.db import models
from django.db.models import Q
from django.contrib.auth.models import User

import os, traceback, random
from datetime import datetime, date, timedelta

from business_manager.python_common.log_client import CommonLog as Log
from business_manager.order.apply_models import Apply, CheckApply
from business_manager.review.models import Review, ReviewRecord, CollectionRecord
from business_manager.employee.models import Employee
from business_manager.review.employee_models import get_dispatch_collector_list, get_employee, get_dispatch_M1_collector_list, get_dispatch_M2_collector_list, get_dispatch_M3_collector_list
from business_manager.collection.models import RepaymentInfo
import MySQLdb

class Command(BaseCommand):
    def handle(self, *args, **options):
        self.user_dict = {29: 'cyb',
                          28: 'rc',
                          27: 'wta',
                          26: 'lxl',
                          25: 'zyl'}
        self.conn = MySQLdb.connect(host = 'rm-bp1i771wb378222ek.mysql.rds.aliyuncs.com', user = 'dingdang', passwd = 'Dingdang123', db = 'dingdangtest2', charset = 'utf8')
        cursor = self.conn.cursor()
        cursor.execute('select * from review_collectionrecords')
        collection_records = cursor.fetchall()
        for collection_record in collection_records:
            record_type = collection_record[1]
            create_at = collection_record[5]
            create_by_id = collection_record[6]
            apply_id = collection_record[7]
            cursor.execute('select * from apply where id={0}'.format(int(apply_id)))
            apply_info = cursor.fetchone()
            repayment_id = apply_info[8]
            cursor.execute('select * from repaymeninfo where id={0}'.format(int(repayment_id)))
            repayment_info = cursor.fetchone()
            order_number = repayment_info[1]

            user = User.objects.get(username = self.user_dict[create_by_id])
            collector = Employee.objects.filter(user = user)
            repayment = RepaymentInfo.objects.filter(order_number = order_number)
            if not repayment:
                print 'repayment not exist:', order_number
                continue
            apply = Apply.objects.filter(repayment = repayment[0])
            if not apply:
                print 'apply not exist:', order_number
                continue
            apply = apply[0]

            if record_type == '3':
                #dispatch type, dispatch
                record = CollectionRecord(record_type=CollectionRecord.DISPATCH, object_type=CollectionRecord.SELF,
                                         create_by = collector[0], collection_note=u"管理员 将客户分配给 %s" % collector[0].username,
                                         promised_repay_time=None, apply=apply, create_at = create_at)
                record.save()
                reviews = Review.objects.filter(order = apply).order_by("-id")
                if len(reviews) > 0:
                    review = reviews[0]
                    review.reviewer = collector[0]
                    review.save()
                else:
                    review = Review()
                    review.reviewer = collector[0]
                    review.create_at = datetime.now()
                    review.order = apply
                    review.review_res = 'i'
                    review.save()
                apply.status = apply_info[6]
                apply.save()
            else:
                record = CollectionRecord(record_type = record_type, object_type = collection_record[2], create_by = collector[0],
                                         collection_note = collection_record[3], promised_repay_time = collection_record[4],
                                         create_at = create_at, apply = apply)
                record.save()

        apply_list = cursor.execute('select * from apply').fetchall()
        for apply_info in apply_list:
            repayment_id = apply_info[8]
            repayment_info = cursor.execute('select * from repaymeninfo where id={0}'.format(int(repayment_id))).fetchone()
            order_number = repayment_info[1]
            repayment = RepaymentInfo.objects.filter(order_number = order_number)
            if not repayment:
                print 'repayment not exist:', order_number
                continue
            apply = Apply.objects.filter(repayment = repayment[0])
            if not apply:
                print 'apply not exist:', order_number
                continue
            apply = apply[0]
            apply.status = apply_info[6]
            apply.save()


