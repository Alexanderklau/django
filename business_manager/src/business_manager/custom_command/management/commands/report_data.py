# -*- coding: utf-8 -*-
"""
数据上报:

    补报数据, 一天一个 json 文件

"""


from django.core.management.base import BaseCommand, CommandError
from django.db import models

import os, traceback, random
from datetime import datetime
import time
import json

import arrow

from business_manager.review import message_client, risk_client, redis_client
from business_manager.order.apply_models import Apply, CheckApply
from business_manager.review.models import Review, ReviewRecord, CollectionRecord
from business_manager.collection.models import *

from business_manager.collection.batch_import import report_data_repay

from business_manager.import_data.services import report_data_collection_money
from business_manager.employee.models import Employee


def get_money(apply):
    print 'in get money'
    # repayment = apply.repayment
    # all_ins = InstallmentDetailInfo.objects.filter(repayment=repayment)
    # money = sum([ins.ori_should_repay_amount for ins in all_ins if ins.repay_status == 2]) / 100.0
    next_apply = Apply.objects.filter(repayment=apply.repayment, money__gt=apply.money).order_by('id').first()
    installment_number = apply.money + 1
    installments = InstallmentDetailInfo.objects.filter(
        repayment=apply.repayment, installment_number__gte=installment_number)
    if next_apply:
        print next_apply
        print 'nnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnn'
        installments = InstallmentDetailInfo.objects.filter(
            repayment=apply.repayment, installment_number__gte=installment_number, installment_number__lt=next_apply.money + 1)

    print 'installments count: %s' % installments.count()
    # if installments.count() != 1:
        # print 'error: installments count: %s' % installments.count()
    # money = sum([ins.ori_should_repay_amount for ins in installments]) / 100.0
    money = apply.rest_repay_money / 100.0

    print 'out get_money'
    return money


def get_collector_id(apply):
    print 'in get_collector_id'

    q = {
        'record_type': '3',
        'create_at__lt': apply.create_at,
        'apply': apply,
    }
    collector_id = ''

    collection_record = CollectionRecord.objects.filter(**q).order_by('-id').first()
    if collection_record:
        collection_note = collection_record.collection_note
        name = collection_note.split(' ')[-1].strip()
        print 'name'
        print name
        employee = Employee.objects.filter(username=name).first()
        if employee:
            collector_id = employee.user.username
        else:
            print 'error: name: %s, apply: %s' % (name, apply)

    # collector_id = apply.employee.user.username


    print 'out get_collector_id'

    return collector_id


def get_assign_date(apply):
    print 'in get_assign_date'

    create_at = arrow.get(apply.create_at).replace(months=-1).naive
    assign_date = int(time.mktime(create_at.timetuple()))
    print 'out get_assign_date'

    return assign_date




def report_data_repay_success(today):
    """催收回款数据上报

    """
    print 'in report_data_repay_success'
    path = '/home/dengzhehao/data'
    all_files = os.listdir(path)
    files = [f for f in all_files if today.strftime('%Y-%m-%d') in f]
    print today
    print files
    repay_data = []
    for _f in files:
        with open(os.path.join(path, _f)) as f:
            data = json.load(f)
            repay_data.extend(data['actual_collection_data'])

    print len(repay_data)
    print '-------------'
    report_datas = report_data_repay(repay_data)
    repeat_datas = []
    applys_id = {}
    for rd in repeat_datas:
        aid = rd['fields']['apply_id']
        if aid in applys_id:
            repeat_datas.append(rd)
        applys_id[aid] = 1
    
    print 'repeat_datas'
    print repeat_datas
    filename = '%s_hk.json' % today.strftime('%Y-%m-%d')
    print filename
    with open(filename, 'w') as fp:
        for data in report_datas:
            fp.write('%s\n' % json.dumps(data))



def report_data_trans(start_time, end_time):
    """已流转 状态的 数据上报

    需要将 data_report_client.report_data() 注释掉.
    """
    report_datas = []
    today = start_time
    endtime = end_time
    fields = {
        "spend_time": 0,
        "money": '',
    }
    tags = {
        "status": u"已流转",
        "collector_id": "",
    }
    now_time = int(time.mktime(today.timetuple()) * pow(10, 9))
# timestamp = int(time.time() * pow(10, 9))

    q = dict(
        create_at__gte=today,
        create_at__lt=endtime,
        type__in=['c', 'd', 'e', 'g', 'h']
    )
    type_dic = {
        'm2': 'm1',
        'm3': 'm2',
        'm4': 'm3',
        'm5': 'm4',
        'm5+': 'm5',
    }
    applys = Apply.objects.filter(**q)
    print applys.count()
    print applys
    for apply in applys:
        data = report_data_collection_money(apply)

        money = get_money(apply)
        collector_id = get_collector_id(apply)
        assign_date = get_assign_date(apply)
        print money
        fields['money'] = money
        fields['assign_date'] = assign_date
        tags['collection_type'] = type_dic.get(data['tags']['collection_type'], data['tags']['collection_type'])
        tags['collector_id'] = collector_id

        data['fields'].update(fields)
        data['tags'].update(tags)
        data['time'] = now_time

        print data
        report_datas.append(data)

    filename = '%s_trans.json' % today.strftime('%Y-%m-%d')
    print filename
    with open(filename, 'w') as fp:
        for data in report_datas:
            fp.write('%s\n' % json.dumps(data))







def report_data_wait(start_time, end_time):
    """待分配状态的 数据上报

    需要将 data_report_client.report_data() 注释掉.
    """
    report_datas = []
    today = start_time
    endtime = end_time
    fields = {
        "spend_time": 0,
        "money": '',
    }
    tags = {
        "status": u"待分配",
        "collector_id": "",
    }
    now_time = int(time.mktime(today.timetuple()) * pow(10, 9))
# timestamp = int(time.time() * pow(10, 9))

    q = dict(
        create_at__gte=today,
        create_at__lt=endtime,
    )
    applys = Apply.objects.filter(**q)
    print applys.count()
    print applys
    for apply in applys:
        data = report_data_collection_money(apply)

        money = get_money(apply)
        print money
        fields['money'] = money
        data['fields'].update(fields)
        data['tags'].update(tags)
        data['time'] = now_time

        print data
        report_datas.append(data)

    filename = '%s.json' % today.strftime('%Y-%m-%d')
    print filename
    with open(filename, 'w') as fp:
        for data in report_datas:
            fp.write('%s\n' % json.dumps(data))



class Command(BaseCommand):

    def handle(self, *args, **options):
        try:
            start_time = arrow.get(2016, 11, 8)
            end_time = arrow.get(2016, 11, 9)
            print end_time - start_time
            _start_time = start_time
            for day in range((end_time-start_time).days):
                print day
                print _start_time
                _end_time = _start_time.replace(days=1)
                print _end_time

                # report_data_repay_success(_start_time.naive)
                # report_data(_start_time.naive, _end_time.naive)
                report_data_trans(_start_time.naive, _end_time.naive)
                _start_time = _end_time

        except Exception, e:
            print e

