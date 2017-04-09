#!/usr/bin/env python
# coding=utf-8

from django.core.management.base import BaseCommand, CommandError
from django.db import models
from django.db.models import Q
from django.contrib.auth.models import User as AuthUser

import os, traceback, random
from datetime import datetime, date, timedelta

from business_manager.python_common.log_client import CommonLog as Log
from business_manager.order.apply_models import Apply, CheckApply
from business_manager.review.models import Review, ReviewRecord, CollectionRecord
from business_manager.employee.models import Employee
from business_manager.review.employee_models import get_dispatch_collector_list, get_employee, get_dispatch_M1_collector_list, get_dispatch_M2_collector_list, get_dispatch_M3_collector_list
from business_manager.collection.models import RepaymentInfo, InstallmentDetailInfo
from business_manager.order.models import User, CheckStatus, Profile, IdCard, ContactInfo, BankCard
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
        cursor.execute("select * from apply where status='8' or status='9'")
        apply_list = cursor.fetchall()
        for apply_info in apply_list:
            repayment_id = apply_info[8]
            cursor.execute('select * from repaymeninfo where id={0}'.format(repayment_id))
            repayment_info = cursor.fetchone()
            cursor.execute('select * from installmentdetailinfo where repayment_id={0}'.format(repayment_info[0]))
            installment_info_list = cursor.fetchall()
            order_number = repayment_info[1]
            repayment = RepaymentInfo.objects.filter(order_number = order_number)
            if not repayment:
                #如果不存在，增加记录
                #首先增加user
                cursor.execute('select * from user where id={0}'.format(apply_info[1]))
                user_info = cursor.fetchone()
                cursor.execute('select * from profile where owner_id={0}'.format(user_info[0]))
                profile_info = cursor.fetchone()
                cursor.execute('select * from idcard where owner_id={0}'.format(user_info[0]))
                idcard_info = cursor.fetchone()
                cursor.execute('select * from contactinfo where owner_id={0}'.format(user_info[0]))
                contact_list_info = cursor.fetchall()
                cursor.execute('select * from bankcard where owner_id={0}'.format(user_info[0]))
                bankcard_info = cursor.fetchone()
                cursor.execute('select * from review_collectionrecord where apply_id={0}'.format(apply_info[0]))
                collection_record_info_list = cursor.fetchall()

                user = User.objects.filter(Q(channel = u'叮当钱包（等额本息）') & Q(phone_no = user_info[3]))
                if not user:
                    try:
                        user = User()
                        user.name = user_info[1]
                        user.password = 'e10adc3949ba59abbe56e057f20f883e'
                        user.phone_no = user_info[3]
                        user.id_no = user_info[4]
                        user.channel =  u'叮当钱包（等额本息）'
                        user.create_time = user_info[22]
                        user.is_register = 1
                        user.save()

                        if profile_info:
                            profile = Profile(owner = user, gender = profile_info[2], job = profile_info[3], marriage = profile_info[4],
                                             company="", work_post="", company_phone=profile_info[8], family_address = profile_info[9],
                                             work_address = profile_info[7], email = profile_info[11], qq = '')
                            profile.save()
                        if idcard_info:
                            idcard = IdCard(owner = user, front_pic = idcard_info[2], back_pic = idcard_info[3], handle_pic = idcard_info[4])
                            idcard.save()
                        CheckStatus(owner=user, apply_status=CheckStatus.APPROVAL, profile_status=16405, profile_check_status=16405, credit_limit=100000, real_id_verify_status=5, auto_check_status = 0).save()
                        if contact_list_info:
                            for contact_info in contact_list_info:
                                c = ContactInfo(owner = user, name = contact_info[1], relationship = contact_info[5], phone_no = contact_info[4])
                                c.save()

                        #生成银行卡信息
                        if bankcard_info:
                            bankcard = BankCard(owner = user, card_number = bankcard_info[1], bank_type = bankcard_info[3],
                                               bank_name = bankcard_info[6])
                            bankcard.save()
                    except Exception,e:
                        print 'create user failed:',e
                else:
                    user = user[0]

                #生成贷款信息
                repayment = RepaymentInfo()
                repayment.order_number = order_number
                repayment.repay_status = RepaymentInfo.OVERDUE
                repayment.apply_amount = repayment_info[3]
                repayment.exact_amount = repayment_info[4]
                repayment.repay_amount = repayment_info[5]
                repayment.rest_amount = repayment_info[18]
                repayment.user = user
                repayment.strategy_id = repayment_info[7]

                bankcard = BankCard.objects.filter(owner = user).first()
                repayment.bank_card = user.bankcard
                repayment.apply_time = repayment_info[11]
                repayment.first_repay_day = repayment_info[12]
                repayment.reason = ''
                repayment.overdue_days = repayment_info[16]
                repayment.save()

                for installment_info in installment_info_list:
                    detail = InstallmentDetailInfo(repayment = repayment,
                                                  installment_number = installment_info[2],
                                                  should_repay_time = installment_info[3],
                                                  real_repay_time = installment_info[4],
                                                  should_repay_amount = installment_info[5],
                                                  real_repay_amount = installment_info[6],
                                                  reduction_amount = installment_info[7],
                                                  repay_status = installment_info[8],
                                                  repay_channel = installment_info[9],
                                                  repay_overdue = installment_info[10],
                                                  repay_principle = installment_info[11],
                                                  repay_overdue_interest = installment_info[12],
                                                  repay_penalty = installment_info[13],
                                                  repay_bank_fee = installment_info[14],
                                                  repay_interest = installment_info[15],
                                                  repay_fee = installment_info[16],
                                                  overdue_days = installment_info[17],
                                                  order_number = installment_info[18])
                    detail.save()
                apply = Apply(create_by = user, create_at = apply_info[2], last_commit_at = apply_info[3],
                             finish_time = apply_info[4], money = apply_info[5], status = apply_info[6],
                             type = apply_info[7], repayment = repayment, pic = apply_info[9],
                             experiment = apply_info[10], flow_id = apply_info[11], product = apply_info[12],
                             salesman = apply_info[13], strategy_id = apply_info[14], amount = apply_info[15],
                             reason = apply_info[16], bill_address = apply_info[17])
                apply.save()

                for collection_record_info in collection_record_info_list:
                    auth_user = User.objects.get(username = self.user_dict[collection_record_info[6]])
                    collector = Employee.objects.filter(user = auth_user)
                    collection_record = CollectionRecord(record_type = collection_record_info[1],
                                                        object_type = collection_record_info[2],
                                                        collection_note = collection_record_info[3],
                                                        promised_repay_time = collection_record_info[4],
                                                        create_at = collection_record_info[5],
                                                        create_by = collector[0],
                                                        apply = apply)
                    collection_record.save()
                    if collection_record_info[1] == '3':
                        review = Review()
                        review.reviewer = collector[0]
                        review.create_at = datetime.now()
                        review.order = apply
                        review.review_res = 'i'
                        review.save()








