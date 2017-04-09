# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand, CommandError
from django.db import models

import os, traceback, random
from datetime import datetime

from business_manager.review import message_client, redis_client
from business_manager.python_common.log_client import CommonLog as Log
from business_manager.order.apply_models import Apply, CheckApply
from business_manager.review.models import Review,  ReviewRecord, CollectionRecord
# from business_manager.review.employee_models import get_dispatch_collector_list, get_employee
from business_manager.collection.models import *

from django.conf import settings
from business_manager.order_management_server.order_management_client import OrderClient
risk_client = OrderClient(settings.RISK_SERVER["HOST"], settings.RISK_SERVER["PORT"], time_out=150000)


class Command(BaseCommand):
    def _get_installment_by_apply(self, re_apply):
        '''
            根据repay apply获取对应的installment
        '''
        repayment = re_apply.repayment
        installments = InstallmentDetailInfo.objects.filter(repayment=repayment, installment_number=re_apply.money + 1)
        installment = None
        if len(installments) == 1:
            installment = installments[0]
        return installment

    def _dispatch_collection(self, c_apply, staff):
        '''
            将c_apply 分配给staff
        '''
        Log().info(u"%s got collection review: %d)%s" %(staff.username, c_apply.id, c_apply.create_by.name))
        record = CollectionRecord(record_type=CollectionRecord.DISPATCH, object_type=CollectionRecord.SELF, create_by = staff,
                              collection_note=u"管理员 将客户分配给 %s" % (staff.username), promised_repay_time=None, apply=c_apply)
        record.save()
        reviews = Review.objects.filter(order = c_apply).order_by("-id")
        if len(reviews) > 0:
            review = reviews[0]
            review.reviewer = staff
            review.save()
        else: #没有review 新建
            review = Review()
            review.reviewer = staff
            review.create_at = datetime.now()
            review.order = c_apply
            review.review_res = 'i'
            review.save()
        c_apply.status = 'i'
        c_apply.save()
        Log().info(u"%s got collection review: %d)%s success" %(staff.username, c_apply.id, c_apply.create_by.name))

    def _get_random_collector(self, collectors):
        size = len(collectors)
        return collectors[random.randint(0, size-1)]

    def handle(self, *args, **options):
        try:
            # 1. check_loan
            today = datetime.today().strftime("%Y-%m-%d")
            Log().info("daily_loan %s" % today)
            try:
                res = risk_client.check_loan(today)
                print res
                Log().info("daily_loan %s" % str(res))
            except:
                traceback.print_exc()
                Log().error("check loan excp:%s" % str(e))

            print 'aaaaaaaaaaa'
            # collectors = get_dispatch_collector_list()
            # #for collector in collectors:
            # #    Log().info(collector.username)

            # collection_applys = Apply.objects.filter(type=Apply.COLLECTION_M0, status=Apply.WAIT)
            # print 'cccccccccccccc'
            # print collection_applys
            # #collection_applys = Apply.objects.filter(status=Apply.PROCESSING)

            # for c_apply in collection_applys:
                # installment = self._get_installment_by_apply(c_apply)
                # print "installment"
                # print installment
                # if installment:
                    # print c_apply.id, installment.should_repay_time.strftime("%m-%d"), c_apply.create_by.phone_no
                    # #2 dispatch collection
                    # # staff = self._get_random_collector(collectors)
                    # # print staff, staff.id
                    # # self._dispatch_collection(c_apply, staff)
                    # #3 send message
                    # token = "%s_%s" % (today, c_apply.create_by.name)
                    # ret = redis_client.hsetnx("pay_token", token, 1)
                    # if ret == 0: #token已经存在
                        # Log().info("skip duplicate message sending %s" % token)
                    # else:
                        # Log().info("send message: %s" % token)
                        # message_client.send_message(c_apply.create_by.phone_no, (u"您有一笔借款%s到期，请保证银行卡中资金充足。多谢您的合作--陆鹏" % (installment.should_repay_time.strftime("%m-%d"))).encode("gbk"), 5)

            Log().info("daily_loan done")

        except Exception, e:
            print e
            traceback.print_exc()
            Log().error("daily loan excp:%s" % str(e))

