#-*- coding: utf-8 -*-
"""
每天定时去获取 预扣款 状态.
0: 扣款成功
1: 审核中
2: 审核通过

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

class Command(BaseCommand):
    def handle(self, *args, **options):
        # repayments = RepaymentInfo.objects.filter(id__gte=3345)
        bank_state = BankStatement.objects.filter(status=1)
        print "start daily_update_pre_repay_status"
        for bs in bank_state:
            pre_order_number = bs.pre_order_number
            pay_platform = 'kuaifutong'
            merchant_id = 'lupeng'
            res = bank_client.trade_status_query(pre_order_number, pay_platform, merchant_id)
            if res:
                retcode = res.retcode
                err_msg = res.err_msg

                print "bank_state: %s, retcode: %s, err_msg: %s" % (bs.id, retcode, err_msg)
                if retcode == 0:
                    print "success:  bank_state: %s, retcode: %s, err_msg: %s" % (bs.id, retcode, err_msg)
                    bs.status = 2
                    bs.save()
            else:
                print "error:  bank_state: %s, retcode: %s, err_msg: %s" % (bs.id, retcode, err_msg)


        print "end daily_update_pre_repay_status"




