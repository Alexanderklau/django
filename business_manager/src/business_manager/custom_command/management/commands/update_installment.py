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
            installment_list = InstallmentDetailInfo.objects.filter(repayment = repayment)
            for i, installment in enumerate(installment_list):
                installment.installment_number = installment_info_list[i][2]
                installment.should_repay_time = installment_info_list[i][3]
                installment.real_repay_time = installment_info_list[i][4]
                installment.should_repay_amount = installment_info_list[i][5]
                installment.real_repay_amount = installment_info_list[i][6]
                installment.reduction_amount = installment_info_list[i][7]
                installment.repay_status = installment_info_list[i][8]
                installment.repay_channel = installment_info_list[i][9]
                installment.repay_overdue = installment_info_list[i][10]
                installment.repay_principle = installment_info_list[i][11]
                installment.repay_overdue_interest = installment_info_list[i][12]
                installment.repay_penalty = installment_info_list[i][13]
                installment.repay_bank_fee = installment_info_list[i][14]
                installment.repay_interest = installment_info_list[i][15]
                installment.repay_fee = installment_info_list[i][16]
                installment.overdue_days = installment_info_list[i][17]
                installment.save()
            break
