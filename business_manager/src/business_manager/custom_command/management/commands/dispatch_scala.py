# -*- coding:utf-8 -*-
import random
from datetime import date, timedelta, datetime

import math
from django.core.management.base import BaseCommand
from business_manager.employee.models import (get_dispatch_collector_list,
                                                     get_dispatch_M1_collector_list,
                                                     get_dispatch_M2_collector_list,
                                                     get_dispatch_M3_collector_list)

from business_manager.order.apply_models import Apply
from business_manager.custom_command.management.commands import base_dispatch
from business_manager.review.models import CollectionRecord
from business_manager.review.models import Review
from business_manager.import_data.services import report_data_collection_money


class Command(BaseCommand):

    help_text = ("usage:"
                 "dispatch_scala: employee_id proportion"
                 "example: python manage.py dispatch_scala m1 2,3,4 50,60,90"
                 )

    collector_map = {'m1': {'collector': get_dispatch_M1_collector_list, 'type': Apply.COLLECTION_M1},
                     'm2': {'collector': get_dispatch_M2_collector_list, 'type': Apply.COLLECTION_M2},
                     'm3': {'collector': get_dispatch_M3_collector_list, 'type': Apply.COLLECTION_M3}}

    def handle(self, *args, **options):
        """
        m1 25,27 50,60
        :param args:
        :param options:
        :return:
        """
        status = args[0]
        employee = args[1] if len(args) >= 2 else ''
        proportion = args[2] if len(args) >= 3 else ''
        employee_list = employee.split(',')
        propor_list = proportion.split(',')
        print('employee: ', employee_list)
        print('propor_list: ', propor_list)
        scala_dispatch = {e: p for e, p in zip(employee_list, propor_list)}
        print 'scala_dispatch: ', scala_dispatch
        self.dispatch_scala(scala_dispatch, status)

    def dispatch_scala(self, employee_dict, status):
        # collectors = self.get_collection_info(status)
        all_applys = self.get_apply(status)
        if not all_applys:
            print('no applys to dispatch')
            return
        all_collector = self.get_collection_info(status)
        collector_info = base_dispatch.Command().dispatch(status, all_collector, all_applys)
        if not collector_info:
            print('no applys to dispatch')
            return
        div_collectors, other_collectors = self.dive_collectors(collector_info, employee_dict)
        new_employee = [item['collector'] for item in other_collectors]
        new_apply, new_div_collectors = balance(div_collectors)
        new_other_collectors = {}
        if new_apply and new_employee:
            new_other_collectors = base_dispatch.Command().dispatch(status, new_employee, new_apply)
        new_collectors = new_other_collectors.values() + new_div_collectors + other_collectors
        # print(new_collectors)
        self.save(new_collectors)
        # self.save(new_collectors)

    def get_collection_info(self, status):
        if status not in self.collector_map.keys():
            return
        collector_func = self.collector_map[status]['collector']
        return collector_func()

    def get_apply(self, status):
        today = date.today()
        tommorrow = today + timedelta(1)
        applys = Apply.objects.filter(type=self.collector_map[status]['type'],
                                      status=Apply.WAIT,
                                      create_at__lte=tommorrow, create_at__gte=today)
        # applys = Apply.objects.filter(type=self.collector_map[status]['type'],
        #                               status=Apply.WAIT,
        #                               overdue_days__gte=4)
        # applys = Apply.objects.filter(type=self.collector_map[status]['type'],
        #                              status=Apply.WAIT,
        #                              overdue_days__lte=7)

        return applys

    def save(self, collectors):
        collector_dict = {}
        for ci in collectors:
            key = ci['collector'].id
            if collector_dict.get(key):
                for i in ci:
                    if i != 'collector':
                        collector_dict[key][i] += ci[i]
            else:
                collector_dict[key] = ci
        for ci in collector_dict.values():
            # print ci['count'], ci['amount']
            for apply in ci['apply_id_list']:
                record = CollectionRecord(record_type=CollectionRecord.DISPATCH, object_type=CollectionRecord.SELF,
                                          create_by=ci['collector'],
                                          collection_note=u"管理员 将客户分配给 %s" % ci['collector'].username,
                                          promised_repay_time=None, apply=apply)
                record.save()
                reviews = Review.objects.filter(order=apply).order_by("-id")
                if len(reviews) > 0:
                    review = reviews[0]
                    review.reviewer = ci['collector']
                    review.save()
                else:
                    review = Review()
                    review.reviewer = ci['collector']
                    review.create_at = datetime.now()
                    review.order = apply
                    review.review_res = 'i'
                    review.save()
                apply.status = 'i'
                apply.employee = ci['collector']
                apply.save()

                report_data_collection_money(apply)

                apply.update_at = datetime.now()
                apply.save()

    def dive_collectors(self, collectors, employee_dict):
        propor_collector, other_collector = [], []
        for collector in collectors.values():
            key = str(collector['collector'].id)
            if employee_dict.get(key):
                propor_collector.append({'collector': collector, 'propor': employee_dict[key]})
            else:
                other_collector.append(collector)
        return propor_collector, other_collector


# def dispatch_v1(applys, collectors):
#     """
#     1. 订单量平均 （优先）
#     2. 金额平均 （每人总金额不大于500）
#     """
#     # collector = {'1': {'propor': 100, 'count': 0, 'sum': 0, 'apply': []}}
#     applys = check_apply(applys)
#     dispatch_r1 = base_dispatch_v1(applys, collectors)
#     propor_collectors, other_collectors = dive_collectors(dispatch_r1)
#     dispatch_r2, dispatch_app = dispatch_v2(propor_collectors)
#     dispatch_r3 = base_dispatch_v1(dispatch_app, other_collectors)
#     print("dispatch_r2: ", dispatch_r2)
#     print("dispatch_r3: ", dispatch_r3)
#     return dispatch_r2 + dispatch_r3


def dispatch_v2(collectors):
    map(lambda item: item['apply'].sort(key=lambda i: i.repayment.repay_amount), collectors)
    collectors.sort(key=lambda item: sum([i.repayment.repay_amount for i in item]))
    print(collectors)
    wait_to_redispatch = []
    for collector in collectors:
        amount_sum = float(sum([i.repayment.repay_amount for i in collector['apply']]))
        apply_propors = []
        for app in collector['apply']:
            app_propor = int(round(app.repayment.repay_amount/amount_sum, 2) * 100)
            apply_propors.append([app, app_propor])
    # do some shit
    return collectors, wait_to_redispatch


def base_dispatch_v1(applys, collectors):
    applys.sort(key=lambda item: item.repayment.repay_amount)
    avg_count = len(applys)/len(collectors)
    for collector in collectors:
        count = avg_count
        while count:
            if not applys:
                break
            if count % 2:
                temp_apply = applys.pop(0)
            else:
                temp_apply = applys.pop(-1)
            collector['apply'].append(temp_apply)
            count -= 1
    collectors.sort(key=lambda i: sum([m.repayment.repay_amount for m in i]))
    start = 0
    while applys:
        collectors[start]['apply'].append(applys.pop())
        start += 1
    return collectors


def balance(collectors):
    new_collectors = []
    new_apply = []
    for collector in collectors:
        apply_list = collector['collector']['apply_id_list']
        apply_count = len(apply_list) * int(collector['propor']) / 100
        apply_amount = sum([i.repayment.repay_amount for i in apply_list]) * int(collector['propor']) / 100
        random.shuffle(apply_list)
        new_collector_apply, new_apply_list = get_test_near(apply_list, apply_count, apply_amount)
        new_apply += new_apply_list
        count = len(new_collector_apply)
        amount = sum([i.repayment.repay_amount for i in new_collector_apply])
        new_collectors.append({'collector': collector['collector']['collector'], 'apply_id_list': new_collector_apply,
                               'count': count, 'amount': amount})
    return new_apply, new_collectors


def get_near_apply(apply_list, n, x):
    # random.shuffle(apply_list)
    apply_list.sort(key=lambda item: item.repayment.repay_amount)
    new_apply_list = []
    count = 0
    while apply_list:
        if count >= n:
            break
        count += 1
        new_apply_list.append(apply_list.pop())
        if not apply_list:
            break
        amount_list = [i.repayment.repay_amount for i in apply_list]
        if sum(amount_list) <= x and (sum(amount_list) + apply_list[-1].repayment.repay_amount > x):
            break
    return new_apply_list, apply_list


def get_test_near(apply_list, n, x):
    new_apply_list = sorted(apply_list, key=lambda k: math.fabs(x/2-k.repayment.repay_amount))
    return new_apply_list[:n], new_apply_list[n:]
