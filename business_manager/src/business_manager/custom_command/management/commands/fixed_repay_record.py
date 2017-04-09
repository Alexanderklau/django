#-*- coding: utf-8 -*-
"""
陆鹏: 之前有些单子是没有通过. 管理系统扣款的. 

所以没有对应的 repayrecord, repayinstallmentrecord, apply, installment, repayment 的数据也没有改
"""


from django.core.management.base import BaseCommand, CommandError
from django.db import models
#from placeholders import *
import os
import httplib
import urllib2
import urllib

from business_manager.order.apply_models import Apply, ExtraApply, CheckApply
from business_manager.review.models import Review, ReviewRecord, CollectionRecord, BankStatement, RepayRecord, RepayInstallmentRecord
from business_manager.order.models import BankCard, ContactInfo,CheckStatus, User
from business_manager.strategy.models import Strategy2
from business_manager.collection.models import *
from business_manager.review import message_client, bank_client, risk_client, redis_client

class Command(BaseCommand):
    def handle(self, *args, **options):
        #ori_str = """ 熊志鹏, 15867799112, 100
        #王海洲, 15990658001, 200
        #钟承超, 13432341234, 300 """
        # ori_str = '''张万春,13818568885,868
        # 汤志强,15001717009,868
	# 曹小闯,18721065366,868
        ori_str = '''陆薇,13601787766,868
        张映昭,13903338627,868
        周晓峰,18001909710,868
        程为银,14782413339,1400.02
        乔松,13501925566,868
        张广卫,15021302037,853
        王琦,13918025026,868
        陆威,18616660535,853
        王海华,18721175567,868
        袁倩,18616388760,868
        干志斌,13386166661,868
        林日春,13916204431,868
        殷军,13671719933,868
        吴晓鸿,13918276576,868
        朱洪生,13311722051,702.24
        顾俊,18621685103,868'''
        datas = [line.replace(" ", "").split(',') for line in ori_str.split('\n')]

        for data in datas:
            name, phone_no, amount = data
            amount = int(round(float(amount), 2) * 100)
            errors = []
            try:
                print 
                print phone_no
                user = User.objects.get(phone_no=phone_no)
                repayment = RepaymentInfo.objects.filter(user=user)
                if repayment.count() > 1:
                    errors.append([user, repayment])
                    continue

                repayment = repayment.first()
                print "repayment"
                print repayment
                print repayment.repay_status
                # installment = InstallmentDetailInfo.objects.filter(repayment=repayment, repay_status__in=[1, 2]).first()
                installment = InstallmentDetailInfo.objects.filter(repayment=repayment, installment_number=1).first()
                bank_card = repayment.bank_card

                repay_apply = Apply.objects.filter(repayment=repayment, money=installment.installment_number - 1, type='p').first()
                collect_apply = Apply.objects.filter(repayment=repayment, money__in=[0,-1], type__in=['a', 'b', 'c', 'd', 'e']).first()
                print "apply exist"
                print repay_apply
                print collect_apply

                print installment
                print installment.should_repay_time, installment.repay_fee, installment.repay_status, installment.repay_channel, installment.installment_number
                should_repay_time = installment.should_repay_time
                if not repay_apply:
                    repay_apply_data = dict(
                        create_by=user,
                        repayment=repayment,
                        finish_time=should_repay_time,
                        create_at=should_repay_time,
                        money=installment.installment_number - 1,
                        status='9',
                        type='p',
                        experiment="",
                    )
                    repay_apply = Apply(**repay_apply_data)
                    repay_apply.save()
                else:
                    repay_apply.status = '9'
                    repay_apply.finish_time = should_repay_time
                    repay_apply.save()

                if not collect_apply:
                    collect_apply_data = dict(
                        create_by=user,
                        repayment=repayment,
                        finish_time=should_repay_time,
                        create_at=should_repay_time,
                        money=installment.installment_number - 1,
                        status='8',
                        type='a',
                        experiment="",
                    )
                    collect_apply = Apply(**collect_apply_data)
                    collect_apply.save()
                else:
                    collect_apply.status = '8'
                    collect_apply.finish_time = should_repay_time
                    collect_apply.save()


                repayment.rest_amount = repayment.rest_amount - amount
                repayment.last_time_repay = should_repay_time
                repayment.repay_status = 1
                repayment.save()

                installment.repay_status = 3
                installment.repay_channel = 1
                installment.real_repay_amount = amount
                installment.real_repay_time = should_repay_time
                installment.save()

                print 'dddddddddd'
                repay_record_data = dict(
                        exact_amount=amount,
                        exact_fee=amount,
                        bank_card_id=bank_card.id,
                        create_at=should_repay_time,
                        repayment=repayment,
                        repay_channel=1,
                )
                repay_record = RepayRecord(**repay_record_data)
                repay_record.save()
                print "repay record"
                print repay_record.id

                repay_installment_record_data = dict(
                        repay_record=repay_record,
                        exact_amount=amount,
                        exact_fee=amount,
                        bank_card_id=bank_card.id,
                        create_at=should_repay_time,
                        repayment=repayment,
                        repay_channel=1,
                        installment=installment,
                )
                repay_installment_record = RepayInstallmentRecord(**repay_installment_record_data)
                repay_installment_record.save()
                print "repay_installment_record"
                print repay_installment_record.id

                print user
            except Exception as e:
                print "error"
                print e

            print name
            print amount
            print errors

        pass
