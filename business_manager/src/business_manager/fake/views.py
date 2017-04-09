# -*- coding: utf-8 -*-
from django.views.generic import View
from django.http import HttpResponse

import random,string,uuid,time
import datetime
import json
import os

from business_manager.settings import BASE_DIR
from business_manager.order.models import *
from business_manager.order.apply_models import Apply
from business_manager.collection.models import RepaymentInfo, InstallmentDetailInfo
from business_manager.review.models import Review
from business_manager.util.decorator import *

from business_manager.review import risk_client

# res = risk_client.repay_loan(order_number, 0, 1)
#备注是给用户看的状态, 负数状态用户看不到
REPAY_STATUS_TYPE = {
'reject' : -3, #拒绝
'canceled' : -2, #已取消
'prepare' : -1, #合同待确认 (不要审核的情况, 新版本废弃)
'start' : 0,    #放款中       
'repaying' : 1, #还款中
'overdue' : 2,  #逾期
'done' : 3,     #已完成       
'checking' : 4, #审核中       
'pay_done' : 5, #已放款
'pass' : 6, #通过 (审核通过待确认合同)
'pre_due' : 7, # ---          
'overdue_done' : 8, #完成

}


class FakeUser(View):

    def __init__(self):
        filename = os.path.join(os.path.dirname(__file__), './fake_user.json')
        with open(filename, 'r') as fp:
            user_datas = json.load(fp)

        self.user_datas = user_datas

    def get(self, request, method):
        if method == 'create':
            self.create_user()
            self.create_repayment()
            # 打款成功
            self.create_apply(Apply.PAY_LOAN, Apply.PAY_SUCCESS)
            # 代付
            # self.create_apply(Apply.PAY_LOAN)
            # 打款中
            # self.create_apply(Apply.ASK_MONEY)
        elif method == 'delete':
            self.delete_user()
            pass

        return HttpResponse('%s' % method)

    def create_repayment(self):

        # 逾期10天，逾期30天，逾期59天，逾期80天
        # strategy
        strategy_days = {
            10: 22,
            11: 29,
            15: 31,
        }

        repayment_args = [
            [0, 1557, 10, u'', 0, 0, -80],
            [0, 1557, 10, u'', 0, 0, -59],
            [0, 1557, 10, u'', 0, 0, -30],
            [0, 1557, 10, u'', 0, 0, -10],
            [0, 1557, 10, u'', 0, 0, 0],
            [0, 1557, 10, u'', 0, 0, 2],

            [0, 1557, 11, u'', 0, 0, -80],
            [0, 1557, 11, u'', 0, 0, -59],
            [0, 1557, 11, u'', 0, 0, -30],
            [0, 1557, 11, u'', 0, 0, -30],
            [0, 1557, 11, u'', 0, 0, -10],
            [0, 1557, 11, u'', 0, 0, 0],
            [0, 1557, 11, u'', 0, 0, 2],

            [0, 1557, 15, u'', 0, 0, -80],
            [0, 1557, 15, u'', 0, 0, -59],
            [0, 1557, 15, u'', 0, 0, -30],
            [0, 1557, 15, u'', 0, 0, -10],
            [0, 1557, 15, u'', 0, 0, 0],
            [0, 1557, 15, u'', 0, 0, 2],

        ]
        # keys = [uid, required_amount, strategy_id, purpose, bankcard_id, order_number, day=None]
        arg_index = 0
        args_len = len(repayment_args)
        for _index, _data in enumerate(self.user_datas):
            if int(_data['check_status']['id'][-3:]) not in range(305, 350) or arg_index >= args_len:
                continue

            user_id = _data['user']['id']
            user = User.objects.get(id=user_id)
            bank_card_id = user.bankcard_set.first().id
            order_number = user_id
            repayment_arg = repayment_args[arg_index]
            # print repayment_arg
            # print repayment_arg[6]
            # print datetime.timedelta(days=repayment_arg[6])
            day = datetime.datetime.now() + datetime.timedelta(days=(repayment_arg[6] - strategy_days[repayment_arg[2]]))
            # print day
            # print 'kkkkk'

            repayment_arg[0] = int(user_id)
            repayment_arg[1] = repayment_arg[1] * 100
            repayment_arg[4] = bank_card_id
            repayment_arg[5] = order_number
            repayment_arg[6] = day.strftime('%Y-%m-%d')

            print repayment_arg
            print risk_client.new_repayment(*repayment_arg)
            arg_index += 1

        repayment = RepaymentInfo.objects.filter(user__id__contains='201600')
        for _r in repayment:
            _r.repay_status = REPAY_STATUS_TYPE['pay_done']
            for i in _r.installmentdetailinfo_set.all():
                i.repay_status = REPAY_STATUS_TYPE['pre_due']

            _r.save()

        print repayment
        print '* ' * 100

        print risk_client.check_loan(datetime.datetime.now().strftime('%Y-%m-%d'))


    # def create_repayment(self):
        # risk_client.new_repayment()
        # repayment = {"id": "20160001", "order_number": "20160001", "repay_status": "5", "apply_amount": "160000", "exact_amount": "160000", "repay_amount": "185174", "rest_amount": "185174", "strategy_id": "15", "reason": "应急需要", "apply_time": "2016-03-08 13:56:38", "next_repay_time": "2016-04-09 00:00:00", "bank_card_id": "139988", "user_id": "376101", "first_repay_day": "2016-04-09 16:02:34", "capital_channel_id": "2", "score": "10000", "rest_principle": "160000", "balance": "0", "overdue_days": "0", "overdue_days_total": "0",}
        # installment = [{"id": "20170001", "installment_number": "1", "should_repay_time": "2016-04-09 00:00:00", "should_repay_amount": "61724", "real_repay_amount": "0", "repay_status": "7", "repay_channel": "0", "repayment_id": "20160001", "repay_overdue": "0", "reduction_amount": "0", "repay_principle": "52452", "repay_interest": "2672", "repay_fee": "6400", "repay_overdue_interest": "0", "repay_penalty": "0", "repay_bank_fee": "200", "overdue_days": "0",}, {"id": "20170002", "installment_number": "2", "should_repay_time": "2016-05-09 00:00:00", "should_repay_amount": "61725", "real_repay_amount": "0", "repay_status": "7", "repay_channel": "0", "repayment_id": "20160001", "repay_overdue": "0", "reduction_amount": "0", "repay_principle": "53329", "repay_interest": "1796", "repay_fee": "6400", "repay_overdue_interest": "0", "repay_penalty": "0", "repay_bank_fee": "200", "overdue_days": "0",}, {"id": "20170003", "installment_number": "3", "should_repay_time": "2016-06-09 00:00:00", "should_repay_amount": "61725", "real_repay_amount": "0", "repay_status": "7", "repay_channel": "0", "repayment_id": "20160001", "repay_overdue": "0", "reduction_amount": "0", "repay_principle": "54220", "repay_interest": "905", "repay_fee": "6400", "repay_overdue_interest": "0", "repay_penalty": "0", "repay_bank_fee": "200", "overdue_days": "0",}]

        # for _index, _data in enumerate(self.user_datas):
            # if _data['check_status']['id'][-3:] not in ['305', '306', '307']:
                # continue
            # print 'dddddddddddddd'
            # _repayment = repayment.copy()
            # user_id = _data['user']['id']
            # user = User.objects.get(id=user_id)
            # _repayment.pop('user_id', '')
            # _repayment.pop('bank_card_id', '')
            # _repayment['user'] = user
            # print user
            # _repayment['bank_card'] = user.bankcard_set.first()
            # _repayment['id'] = '2016%05d' % (_index + 1)
            # _repayment['order_number'] = '2016%05d' % (_index + 1)

            # r = RepaymentInfo(**_repayment)
            # r.save()
            # for _i in installment:
                # _index += 1
                # _installment = _i.copy()
                # _installment.pop('repayment_id', '')
                # _installment['repayment'] = r
                # _installment['id'] = '2017%05d' % _index
                # i = InstallmentDetailInfo(**_installment)
                # i.save()

    def create_apply(self, type, status):

        for _data in self.user_datas:
            user_id = _data['user']['id']
            user = User.objects.get(id=user_id)
            apply_dic = {
                "id": user_id,
                "create_by": user,
                "create_at": datetime.datetime.now(),
                # "last_commit_at": ,
                # "finish_time": ,
                "money": 2000,
                "type": type,
                "repayment": user.repaymentinfo_set.first(),
                "status": status,
                # "pic": ,
            }
            applys = Apply(**apply_dic)
            applys.save()
            pass

    def delete_user(self):

        for _data in self.user_datas:
            user_id = _data['user']['id']
            user = User.objects.filter(id=user_id)
            print user
            user.delete()

        # user = User.objects.filter(id__contains='201600')
        # print user
        # user.delete()

    def create_user(self):

        for _data in self.user_datas:
            _data['user'].pop('invitation', '')
            _data['user'].pop('sub_channel', '')
            _data['user']['create_time'] = datetime.datetime.now()
            user = User(**_data['user'])
            user.save()

            print _data['bankcard']

            _data['profile']['owner'] = user
            _data['idcard']['owner'] = user
            _data['check_status']['owner'] = user
            _data['chsi']['user'] = user
            _data['bankcard']['user'] = user
            _data['contact_info']['owner'] = user

            profile = Profile(**_data['profile'])
            profile.save()

            idcard = IdCard(**_data['idcard'])
            idcard.save()

            if int(_data['check_status']['id'][-3:]) in range(305, 350):
                _data['check_status']['credit_limit'] = 2000 * 100
            check_status = CheckStatus(**_data['check_status'])
            check_status.save()

            chsi = Chsi(**_data['chsi'])
            chsi.save()

            bankcard = BankCard(**_data['bankcard'])
            bankcard.save()

            contact_info = ContactInfo(**_data['contact_info'])
            contact_info.save()

        return HttpResponse('ok')


