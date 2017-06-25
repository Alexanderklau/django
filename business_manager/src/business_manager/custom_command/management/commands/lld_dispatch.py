from django.core.management.base import BaseCommand, CommandError
from django.db import models
from django.db.models import Q

import os, traceback, random
from datetime import datetime, date, timedelta

from business_manager.python_common.log_client import CommonLog as Log
from business_manager.order.apply_models import Apply, CheckApply
from business_manager.review.models import Review, Employee, ReviewRecord, CollectionRecord
from business_manager.employee.models import get_dispatch_collector_list,get_employee,get_dispatch_S1_collector_list,get_dispatch_S2_collector_list, get_dispatch_M2_collector_list, get_dispatch_M3_collector_list
from business_manager.collection.models import *
from business_manager.collection.services import collection_extra_data


from business_manager.import_data.services import report_data_collection_money



class Command(BaseCommand):

    def check_installment_by_apply(self, re_apply):
        repayment = re_apply.repayment
        installments = InstallmentDetailInfo.objects.filter(repayment=repayment, installment_number=re_apply.money + 1,
                                                            repay_status=2)
        installment = None
        if not installments:
            print("skip info: ")
            print("current repayment: ", repayment)
            print("current re_apply: ", re_apply)
        if len(installments) >= 1:
            installment = installments[0]
        return installment

    def _get_installment_by_apply(self, re_apply):
        repayment = re_apply.repayment
        installments = InstallmentDetailInfo.objects.filter(repayment=repayment, installment_number=re_apply.money + 1,
                                                            repay_status=2)
        installment = None
        if not installments:
            print("skip info: ")
            print("current repayment: ", repayment)
            print("current re_apply: ", re_apply)
        if len(installments) >= 1:
            installment = installments[0]
            amount = 0
            for tmp in installments:
                amount += tmp.should_repay_amount
            self.overdue_info[re_apply.id] = amount
            self.total_amount += amount
        return installment

    def _dispatch(self, c_apply):
        curr_min_amount = 100000000000
        curr_min_collector = None
        selected_id = 0
        for collector_info in self.collector_info.values():
            if collector_info['count'] <= self.current_count:
                if curr_min_amount > collector_info['amount']:
                    curr_min_amount = collector_info['amount']
                    curr_min_collector = collector_info['collector']
                    selected_id = curr_min_collector.id
        self.collector_info[selected_id]['amount'] += c_apply.repayment.repay_amount
        self.collector_info[selected_id]['count'] += 1
        self.total_count += 1
        self.current_count = self.total_count / len(self.collector_info)

    def _get_next_apply(self, amount, count):
        min_gap = self.avg_amount
        if not self.sort_applys:
            return None
        selected_apply = self.sort_applys[0]
        for apply in self.sort_applys:
            if abs((amount + self.overdue_info[apply.id]) / (count + 1) - self.avg_amount) < min_gap:
                selected_apply = apply
                min_gap = abs((amount + self.overdue_info[apply.id]) / (count + 1) - self.avg_amount)
        if selected_apply:
            self.sort_applys.remove(selected_apply)
        return selected_apply

    def _get_next_collector(self):
        selected_id = 0
        less_list = []
        for i in self.collector_info:
            if self.collector_info[i]['count'] <= self.current_count:
                less_list.append(i)
        if len(less_list) == 1:
            self.current_count += 1
            return less_list[0]
        min_gap = 100000000
        for i in less_list:
            if self.collector_info[i]['amount'] == 0:
                return i
            if min_gap > self.collector_info[i]['amount'] / self.collector_info[i]['count']:
                min_gap = self.collector_info[i]['amount'] / self.collector_info[i]['count']
                selected_id = i
        return selected_id

    def _dispatch2(self):
        while True:
            selected_id = self._get_next_collector()
            selected_apply = self._get_next_apply(self.collector_info[selected_id]['amount'], self.collector_info[selected_id]['count'])
            if not selected_apply:
                break
            self.collector_info[selected_id]['amount'] += self.overdue_info[selected_apply.id]
            self.collector_info[selected_id]['count'] += 1
            self.collector_info[selected_id]['apply_id_list'].append(selected_apply)
            self.total_count += 1

    def _get_not_balance_collector(self):
        max_id, minus_max_id = 0, 0
        max_amount, minus_max_amount = 0, 0
        for collector_id in self.collector_info:
            gap = self.collector_info[collector_id]['amount'] - self.avg_collector_amount
            if gap < minus_max_amount:
                minus_max_id = collector_id
                minus_max_amount = gap
            elif gap > max_amount:
                max_id = collector_id
                max_amount = gap
        if max_amount - minus_max_amount < 50000:
            return 0, 0, 0, 0
        return max_id, minus_max_id, max_amount/2, minus_max_amount/2

    def _exchange_apply(self, max_id, minus_max_id, max_amount, minus_max_amount):
        max_exchange_apply, minus_exchange_apply = None, None
        min_gap = max_amount
        for apply in self.collector_info[max_id]['apply_id_list']:
            gap = self.overdue_info[apply.id] - self.avg_amount
            print gap, min_gap
            if gap > 0 and abs(gap - max_amount) < min_gap:
                min_gap = abs(gap - max_amount)
                max_exchange_apply = apply
        min_gap = abs(minus_max_amount)
        for apply in self.collector_info[minus_max_id]['apply_id_list']:
            gap = self.overdue_info[apply.id] - self.avg_amount
            if gap < 0 and abs(abs(gap) - abs(minus_max_amount)) < min_gap:
                min_gap = abs(abs(gap) - abs(minus_max_amount))
                minus_exchange_apply = apply
        if not max_exchange_apply or not minus_exchange_apply:
            return
        print 'exchange amount:{0}, {1}'.format(self.overdue_info[max_exchange_apply.id], self.overdue_info[minus_exchange_apply.id])
        self.collector_info[max_id]['amount'] = self.collector_info[max_id]['amount'] + self.overdue_info[minus_exchange_apply.id] - self.overdue_info[max_exchange_apply.id]
        self.collector_info[max_id]['apply_id_list'].remove(max_exchange_apply)
        self.collector_info[max_id]['apply_id_list'].append(minus_exchange_apply)
        self.collector_info[minus_max_id]['amount'] = self.collector_info[minus_max_id]['amount'] + self.overdue_info[max_exchange_apply.id] - self.overdue_info[minus_exchange_apply.id]
        self.collector_info[minus_max_id]['apply_id_list'].remove(minus_exchange_apply)
        self.collector_info[minus_max_id]['apply_id_list'].append(max_exchange_apply)

    def _re_balance(self):
        for i in range(10):
            co_id1, co_id2, max_amount, minus_max_amount = self._get_not_balance_collector()
            if co_id1 == 0:
                break
            print 'rebalanced co:{0}, {1} amount:{2}, {3}'.format(co_id1, co_id2, max_amount, minus_max_amount)
            self._exchange_apply(co_id1, co_id2, max_amount, minus_max_amount)
            for ci in self.collector_info.values():
                print ci['count'], ci['amount']

    def handle(self, *args, **options):
        apply_type = args[0] if args else 's1'
        collector_info = self.dispatch(apply_type)
        self.dispatch_save(collector_info)

    def dispatch(self, type=None, assign_collector=None, assign_apply=None):
        try:
            Log().info('begin auto dispatch collection')
            self.collector_info = {}
            self.overdue_info = {}
            self.current_count = 0
            self.total_count = 0
            self.avg_amount = 0
            self.total_amount = 0

            today = date.today()
            tomorrow = date.today() + timedelta(1)
            if type == 's1' or not type:
                collectors = get_dispatch_S1_collector_list()
                query_type = Q(type=Apply.COLLECTION_S1)
            elif type == 's2':
                collectors = get_dispatch_S2_collector_list()
                query_type = Q(type=Apply.COLLECTION_S2)
            elif type == 'm2':
                collectors = get_dispatch_M2_collector_list()
                query_type = !(type=Apply.COLLECTION_M2)
            else:
                collectors = get_dispatch_M3_collector_list()
                query_type = Q(type=Apply.COLLECTION_M3)

            query_status = Q(status=Apply.WAIT)
            query_time = Q(create_at__lte=tomorrow, create_at__gte=today)
            # query_time = Q()
            if assign_apply:
                collection_applys = assign_apply
            else:
                collection_applys = Apply.objects.filter(query_type & query_status & query_time)
            if assign_collector:
                collectors = assign_collector
            for collector in collectors:
                self.collector_info[collector.id] = {'count': 0, 'amount': 0, 'collector': collector,
                                                     'apply_id_list': []}
            print 'applys count:{0} collector count:{1}'.format(len(collection_applys), len(collectors))
            real_applys = []
            for c_apply in collection_applys:
                installment = self._get_installment_by_apply(c_apply)
                if not installment:
                    print("skip apply: ", c_apply, installment)
                if installment:
                    real_applys.append(c_apply)
                    # self._dispatch(c_apply)
            print 'applys count:{0} collector count:{1}'.format(len(real_applys), len(collectors))
            if len(real_applys) == 0:
                Log().error('no apply needs to be dispatched')
                return
            self.avg_amount = self.total_amount / len(real_applys)
            self.avg_collector_amount = self.total_amount / len(collectors)
            self.apply_count = len(real_applys)
            self.sort_applys = sorted(real_applys, key=lambda a: a.repayment.repay_amount)
            self._dispatch2()
            for ci in self.collector_info.values():
                print ci['count'], ci['amount']
            self._re_balance()
            return self.collector_info
        except Exception, e:
            Log().error('auto dispatch collection failed, err:{0}'.format(e))
            print 'error:', e

    def dispatch_save(self, collector_info):
        for ci in collector_info.values():
            for apply in ci['apply_id_list']:
                if apply.employee:
                    print("report invalid")
                    report_data_collection_money(apply, u'失效')
                col = collection_extra_data(apply)
                record = CollectionRecord(record_type=CollectionRecord.DISPATCH, object_type=CollectionRecord.SELF,
                                          create_by=ci['collector'],
                                          collection_note=u"管理员 将客户分配给 %s" % ci['collector'].username,
                                          promised_repay_time=None, apply=apply, **col)
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
