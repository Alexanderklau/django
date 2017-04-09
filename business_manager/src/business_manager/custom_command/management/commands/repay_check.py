#-*- coding: utf-8 -*-
"""
代扣, 需要先通过 扣款平台审核. 人工审核时间 > 2 天. 审核是和 银行卡绑定的. 只要对应银行卡 通过后, 以后就直接通过.
所以需要提前审核, 以后的贷款. 会在生成贷款后.提交审核.

这个是一次性脚本. 提交所审核.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import models
#from placeholders import *
import os
import httplib
import urllib2
import urllib

from business_manager.order.apply_models import Apply, ExtraApply, CheckApply
from business_manager.review.models import Review, ReviewRecord, CollectionRecord, BankStatement
from business_manager.collection.models import *
from business_manager.review import message_client, bank_client, risk_client, redis_client

class Command(BaseCommand):
    def handle(self, *args, **options):
        # repayments = RepaymentInfo.objects.filter(id__gte=3345)
        repayments = RepaymentInfo.objects.all()
        pre_repay_bank_state = []
        repay_bank_state = []
        error_repay = []
        apply = Apply.objects.get(id=229)
        for repayment in repayments:
            print repayment,
            user = repayment.user
            repay_money = 0
            # bank_card = BankCard.objects.get(owner=user)
            bank_card = repayment.bank_card

            bank_state_number = BankStatement.objects.filter(bankcard_id=bank_card).order_by("-id").first()
            bank_order_number = bank_state_number.pre_order_number if bank_state_number else ""
            if bank_order_number:
                pre_repay_bank_state.append((bank_state_number.id, bank_state_number.pre_order_number))
                continue

            if not bank_card.bank_name:
                print "error"
                error_repay.append(bank_state_number)
                continue
            print 
            print "order_number: %s, repay_money: %s, user_id: %s, card_number: %s, user_name: %s, phone_no: %s, bank_name: %s, id_no: %s" % (
                bank_order_number, repay_money, user.id, repayment.bank_card.card_number, user.name, user.phone_no, bank_card.bank_name, user.id_no)
            print 'dddddddddddddd'
            res = bank_client.collect(repay_money, user.id, bank_card.card_number, user.name.encode("utf8"), user.phone_no, bank_card.bank_name.encode("utf8"), 'kuaifutong', 'test_name', 1, '', '', 0, user.id_no, 'lupeng', bank_order_number)
            print '--* --' * 30
            print res
            print '  -* --' * 30
            msg = res.err_msg if  res and res.err_msg else ""
            Log().info(u"repay_for %s %s %s %d %d done " % (bank_card.get_bank_code(), bank_card.card_number, repayment.user.name, repayment.user.id, repay_money ))
            Log().info("do realtime repay res:%s msg:%s" % (res.retcode, msg.decode("utf-8")))

            print "create bank_state"
            order_number = None
            pre_order_number = res.order_number
            status = 1

            repay_bank_state.append(pre_order_number)
            bank_state_data = dict(
                pre_order_number=pre_order_number,
                status=status,
                real_repay_amount=repay_money,
                content=msg,
                apply=apply,
                user=user,
                bankcard=bank_card,
            )
            bank_state = BankStatement(**bank_state_data)
            bank_state.save()

            # if not order_number:
                # return 1, 0, bank_state.id
            Log().info("record bank_state success %s" % bank_state.id)
            # return ret_msg, actual_amount, bank_state.id

        print "pre repay bank state"
        print pre_repay_bank_state
        print "repay bank state"
        print repay_bank_state

