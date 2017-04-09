# -*- coding: utf-8 -*-
"""
叮当委案记录:

    一个月只能有一条 委案数据(type=0)
"""


from django.core.management.base import BaseCommand, CommandError
from django.db import models
from django.db.models import Q, Count

import os, traceback, random
from datetime import datetime
import time
import json

import arrow

from business_manager.review import message_client, risk_client, redis_client
from business_manager.order.apply_models import Apply, CheckApply
from business_manager.review.models import Review, ReviewRecord, CollectionRecord, DingdangRepaymentRecord
from business_manager.collection.models import *

from business_manager.collection.batch_import import report_data_repay

from business_manager.import_data.services import report_data_collection_money
from business_manager.employee.models import Employee


class Command(BaseCommand):
    def aa(self, query_set, q):
        query_set = query_set.values('order_number', 'overdue_type').annotate(c=Count('order_number')).filter(c__gt=1)[:10000]
        order_numbers = [qs['order_number'] for qs in query_set]
        print query_set
        print order_numbers
        print query_set.count()
        for order_number in order_numbers:
            extra_q = {
                'order_number': order_number,
            }
            q.update(extra_q)
            invalid_records = DingdangRepaymentRecord.objects.filter(**q)
            overdue_types = [ir.overdue_type for ir in invalid_records]
            print 'overdue_types'
            print overdue_types
            invalid_records_len = invalid_records.count()
            overdue_types_len = len(set(overdue_types))
            # if invalid_records.count() > 1:
            if invalid_records_len != overdue_types_len:
                print invalid_records.values('order_number', 'installment_order_number', 'overdue_days', 'overdue_type', 'create_at', 'should_repay_amount')
                if invalid_records_len <= 2:
                    lastest_record = invalid_records.order_by('-id').first()
                    invalid_records.update(type=-1)
                    lastest_record.type = 0
                    lastest_record.save()

                else:
                    pre_ins_order_num = invalid_records.first().installment_order_number
                    for invalid_record in invalid_records:
                        ins_order_num = invalid_record.installment_order_number
                        if ins_order_num > pre_ins_order_num:
                            print invalid_record.order_number, invalid_record.installment_order_number, invalid_record.overdue_days, invalid_record.overdue_type, invalid_record.create_at, invalid_record.should_repay_amount
                            pre_ins_order_num = ins_order_num
                        else:
                            invalid_record.type= -1

                        invalid_record.save()
        print 'out aa'

    def handle(self, *args, **options):
        try:
            start_time = datetime(2016, 9, 1)
            end_time = datetime(2016, 10, 1)
            q = {
                'type': 0,
                'overdue_type': 'c',
                'create_at__gte': start_time,
                'create_at__lt': end_time,
            }
            query_set = DingdangRepaymentRecord.objects.filter(**q)
            self.aa(query_set, q)

        except Exception, e:
            print e

