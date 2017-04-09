# -*- coding: utf-8 -*-
import json
from django.db.models import Q
from business_manager.order.apply_models import Apply, CheckApply
from business_manager.order.models import Chsi, CheckStatus, Profile
from business_manager.strategy.models import Strategy2
from business_manager.review.models import Review
from business_manager.employee.models import Employee
from business_manager.python_common.common_date import *
from business_manager.bank_server.db_model.user_model import BankCard
from business_manager.util.data_provider import DataProvider
from business_manager.python_common.log_client import CommonLog as Log
from business_manager.util.permission_decorator import page_permission
from business_manager.employee.models import check_employee
from django.http import HttpResponse, StreamingHttpResponse
from business_manager.review.models import *
from business_manager.collection.models import *
from datetime import datetime

import traceback

class CheckApplyProvider(DataProvider):
    """
        订单复核
    """
    def object_filter(self, request):
        """
            time status 两个选择维度
        """
        stime = get_today()
        etime = get_tomorrow()
        timerange = request.GET.get("time")
        if timerange == "today" :
            stime = get_today()
            etime = get_tomorrow()
        elif timerange == "twodays" :
            stime = get_yestoday()
            etime = get_tomorrow()
        elif timerange == "yestoday" :
            stime = get_yestoday()
            etime = get_today()
        elif timerange == "toweek" :
            stime = get_first_day_of_week()
            etime = get_next_weekday(day=get_first_day_of_week(), i=7)
        elif timerange == "tomonth" :
            stime = get_first_day_of_month()
            etime = get_tomorrow()
        else:
            stime = request.GET.get("stime")
            etime = request.GET.get("etime")

        if timerange == "all" :
            query_time = Q()
        else:
            query_time = Q(create_at__lt = etime, create_at__gt = stime)

        apply_type =request.GET.get("type")
        query_type = None
        if apply_type == "topublic" :
            query_type = Q(type=CheckApply.CHECK_TOPUBLIC)
        elif apply_type == "alipay" :
            query_type = Q(type=CheckApply.CHECK_ALIPAY)
        else :
            query_type = Q()

        apply_status = request.GET.get("status")
        query_status = None
        if apply_status == "waiting" :
            query_status = Q(status=CheckApply.WAIT)
        elif apply_status == "success" :
            query_status = Q(status=CheckApply.CHECK_SUCCESS)
        elif apply_status == "failed" :
            query_status = Q(status=CheckApply.CHECK_FAILED)
        else :
            query_status = Q()

        apply_list = CheckApply.objects.filter(query_time & query_type & query_status)
        return apply_list

    def get_columns(self):
        return [u"申请ID", u"用户ID", u"用户名", u"还款方式", u"提交时间",u"完成时间", u"提交人", u"处理状态", u"操作"]

    def get_query(self):
        return ["id__iexact", "repayment__user__id__iexact", "repayment__user__name__icontains", "repayment__user__phone_no__iexact", "repayment__order_number__iexact"]

    def fill_data(self, query_set):
        data_set = []
        today = datetime.combine(date.today(), datetime.max.time())
        for result in query_set.values():
            apply = CheckApply.objects.get(pk = result["id"])
            print apply
            staff = apply.create_by
            user = apply.repayment.user
            operation_url = u"<a class='do_check' name='%d' href='#'>复核</a>" % (apply.id)
            data = {'id': apply.id,
                    "uid": user.id,
                    "username": user.name,
                    "repay_type": apply.get_type_display(),
                    "create_at": apply.create_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "finish_time":str(apply.finish_time),
                    "staff": staff.username,
                    "status": apply.get_status_display(),
                    "operation": operation_url}
            data_set.append(data)
        return data_set

class ReceivablesProvider(DataProvider):
    def object_filter(self, request):
        stime = get_today()
        etime = get_tomorrow()
        timerange = request.GET.get("time")
        if timerange == "today" :
            stime = get_today()
            etime = get_tomorrow()
        elif timerange == "twodays" :
            stime = get_yestoday()
            etime = get_tomorrow()
        elif timerange == "yestoday" :
            stime = get_yestoday()
            etime = get_today()
        elif timerange == "toweek" :
            stime = get_first_day_of_week()
            etime = get_tomorrow()
        elif timerange == "tomonth" :
            stime = get_first_day_of_month()
            etime = get_tomorrow()
        else:
            stime = request.GET.get("stime")
            etime = request.GET.get("etime")

        if timerange == "all" :
            self.query_time = Q()
        else:
            self.query_time = Q( should_repay_time__lt = etime, should_repay_time__gte = stime)

        #print self.query_time
        query_status = Q(repay_status__in=['3','8','7','9','1','2'])
        installments = InstallmentDetailInfo.objects.filter(query_status & self.query_time)
        #query_status = Q(status='y')
        #apply_list = Apply.objects.filter(query_status).distinct()
        #for apply in apply_list:
        #    if apply.repayment:
        #        repayment = apply.repayment
        return installments

    def get_columns(self):

        return [u"订单号", u"姓名", u"身份证号", u"应收日期", u"借款金额", u"借款期数", u"应收期数", u"应收服务费", u"逾期天数", u"应收逾期费用", u"应收逾期罚金", u"应收提前还款违约金", u"应收总额"] #u"应还本息合计"
    
    def get_query(self):
        return ["id__iexact", "repayment__user__name__icontains", "repayment__user__phone_no__icontains", "repayment__user__id_no__icontains"]

    def fill_data(self, query_set):
        data_set = []
        for installment in query_set:
            repayment = installment.repayment
            user = repayment.user
            apply = Apply.objects.filter(repayment = repayment).first()
            if not apply:
                continue
            data = {
                'id': apply.id,
                'username': user.name,
                'idcard': user.id_no,
                'receivables_data': installment.should_repay_time.strftime('%Y-%m-%d'),
                'amount': repayment.apply_amount / 100.00,
                'loan_series':  Strategy2.objects.get(strategy_id=apply.strategy_id).installment_count if apply.strategy_id else 1,
                'receivables_loan_series': installment.installment_number,
                'receivables_service': installment.repay_fee / 100.00,
                'over_due_days': installment.overdue_days,
                'receivables_over_due_pay': installment.repay_overdue_interest / 100.00,
                'receivables_over_due_fine': installment.repay_penalty / 100.00 if installment.repay_penalty else 0,
                'receivables_break_fine': 0,
                'receivables_amount': (installment.should_repay_amount + installment.repay_overdue_interest) / 100.00
            }
            data_set.append(data)
        return data_set
        #for result in query_set:
        #    if result.repayment_id:
        #        print result.repayment_id
        #        user = User.objects.get(id=result.create_by_id)
        #        repayment_obj = RepaymentInfo.objects.get(id=result.repayment_id)
        #        query_id = Q(repayment_id=repayment_obj.id)
        #        query_status = Q(repay_status__in=['3','8', '7','9','1'])
        #        installments = InstallmentDetailInfo.objects.filter(query_id & query_status & self.query_time)
        #        print installments
        #        repayment_id_list = installments.values_list('repayment_id', flat=True).distinct()
        #        installments_list = []
        #        for i in repayment_id_list:
        #            l = installments.filter(repayment_id=i)
        #            installments_list.append(l)
        #        for installments_set in installments_list:
        #            advance_set = installments_set.filter(repay_status='9')
        #            normal_status = Q(repay_status__in=['3','8','7','1'])
        #            normal_set = installments_set.filter(normal_status)
        #            for installment in normal_set:
        #                data = {
        #                    "id":result.id,
        #                    "username": user.name,
        #                    # "idcard": BankCard.objects.filter(owner_id=user.id)[0].card_number,
        #                    "idcard": user.id_no,
        #                    "receivables_data": installment.should_repay_time.strftime("%Y-%m-%d"),
        #                    "amount":  result.repayment.apply_amount/100.00,
        #                    "loan_series": Strategy2.objects.get(strategy_id=result.strategy_id).installment_count if result.strategy_id!=0 else 1,
        #                    "receivables_loan_series": installment.installment_number,
        #                    # "received_service": apply.repayment.apply_amount/100.0,
        #                    "receivables_service": installment.repay_fee/100.00,
        #                    "over_due_days": installment.overdue_days,
        #                    "receivables_over_due_pay": installment.repay_overdue_interest/100.00,
        #                    "receivables_over_due_fine": installment.repay_penalty/100.00 if installment.repay_penalty else 0,
        #                    "receivables_break_fine": 0,
        #                    "receivables_amount": (installment.repay_fee+installment.repay_overdue)/100.00,
        #                    # "operation": operation_url
        #                }
        #                data_set.append(data)
        #            if advance_set.count() > 0:
        #                print 'fdfdsfdsafdasf'
        #                advance_amount = 0
        #                installment = advance_set[0]
        #                for n in advance_set:
        #                    advance_amount = advance_amount +  Repayinstallmentrecord.objects.get(installment_id=n.id).exact_amount
        #                data = {
        #                        "id":result.id,
        #                        "username": user.name,
        #                        # "idcard": BankCard.objects.filter(owner_id=user.id)[0].card_number,
        #                        "idcard": user.id_no,
        #                        "receivables_data": installment.should_repay_time.strftime("%Y-%m-%d"),
        #                        "amount":  result.repayment.apply_amount/100.00,
        #                        "loan_series": Strategy2.objects.get(strategy_id=result.strategy_id).installment_count if result.strategy_id!=0 else 1,
        #                        "receivables_loan_series": installment.installment_number,
        #                        "receivables_service": installment.repay_fee/100.00,
        #                        "over_due_days": installment.overdue_days,
        #                        "receivables_over_due_pay": installment.repay_overdue_interest,
        #                        "receivables_over_due_fine": installment.repay_penalty/100.00 if installment.repay_penalty else 0,
        #                        "receivables_break_fine": advance_amount/100.00,
        #                        "receivables_amount": (installment.repay_fee+installment.repay_overdue+advance_amount)/100.00,                            }
        #                data_set.append(data)
        #return data_set

def get_autdit_receivables_datatable(request):
    return ReceivablesProvider().get_datatable(request)

class ReceivedProvider(DataProvider):
    def object_filter(self, request):
        stime = get_today()
        etime = get_tomorrow()
        timerange = request.GET.get("time")
        if timerange == "today" :
            stime = get_today()
            etime = get_tomorrow()
        elif timerange == "twodays" :
            stime = get_yestoday()
            etime = get_tomorrow()
        elif timerange == "yestoday" :
            stime = get_yestoday()
            etime = get_today()
        elif timerange == "toweek" :
            stime = get_first_day_of_week()
            etime = get_tomorrow()
        elif timerange == "tomonth" :
            stime = get_first_day_of_month()
            etime = get_tomorrow()
        else:
            stime = request.GET.get("stime")
            etime = request.GET.get("etime")

        if timerange == "all" :
            self.query_time = Q()
        else:
            self.query_time = Q(real_repay_time__lt = etime, real_repay_time__gte = stime)
        query_status = Q(repay_status__in=['3','8', '9'])
        installments = InstallmentDetailInfo.objects.filter(query_status & self.query_time)

        return installments

    def get_columns(self):
        return [u"订单号", u"姓名", u"身份证号", u"实收日期", u"借款金额", u"借款期数", u"实收期数", u"实收服务费" ,u"逾期天数", u"实收逾期费用", u"实收逾期罚金", u"实收提前还款违约金", u"实收总额"] #u"应还本息合计"

    def get_query(self):
        # return ["id__iexact", "repayment__user__name__icontains", "repayment__user__phone_no__icontains"]
        return ["id__iexact", "repayment__user__name__icontains", "repayment__user__phone_no__icontains", "repayment__user__id_no__icontains"]

    def fill_data(self, query_set):
        data_set = []
        for installment in query_set:
            repayment = installment.repayment
            user = repayment.user
            apply = Apply.objects.filter(repayment = repayment)[0]
            _strategy2 = Strategy2.objects.filter(strategy_id=apply.strategy_id)
            data = {
                'id': apply.id,
                'username': user.name,
                'idcard': user.id_no,
                'received_data': installment.real_repay_time.strftime('%Y-%m-%d'),
                'amount': repayment.apply_amount / 100.00,
                'loan_series':  _strategy2[0].installment_count if apply.strategy_id!=0 and _strategy2 else 1,
                'received_loan_series': installment.installment_number,
                'received_service': installment.repay_fee / 100.00,
                'over_due_days': installment.overdue_days,
                'received_over_due_pay': installment.repay_overdue_interest / 100.00,
                'received_over_due_fine': installment.repay_penalty / 100.00 if installment.repay_penalty else 0,
                'received_break_fine': 0,
                'received_amount': installment.real_repay_amount / 100.00
            }
            data_set.append(data)
        return data_set

        #for result in query_set:
        #    print '8'*20
        #    print result.repayment_id
        #    if result.repayment_id:
        #        user = User.objects.get(id=result.create_by_id)
        #        repayment_obj = RepaymentInfo.objects.get(id=result.repayment_id)
        #        query_id = Q(repayment_id=repayment_obj.id)
        #        query_status = Q(repay_status__in=['3','8','9'])
        #        installments = InstallmentDetailInfo.objects.filter(query_id & query_status & self.query_time)
        #        repayment_id_list = installments.values_list('repayment_id', flat=True).distinct()
        #        installments_list = []
        #        for i in repayment_id_list:
        #            l = installments.filter(repayment_id=i)
        #            installments_list.append(l)
        #        print '---*'*20
        #        print installments_list
        #        repayment_tmp_id = -1
        #        for installments_set in installments_list:
        #            advance_set = installments_set.filter(repay_status='9')
        #            normal_status = Q(repay_status__in=['3','8'])
        #            normal_set = installments_set.filter(normal_status)
        #            for installment in normal_set:
        #                print 'gg'
        #                data = {
        #                    "id":result.id,
        #                    "username": user.name,
        #                    # "idcard": BankCard.objects.filter(owner_id=user.id)[0].card_number,
        #                    "idcard": user.id_no,
        #                    "received_data": installment.real_repay_time.strftime("%Y-%m-%d"),
        #                    "amount":  result.repayment.apply_amount/100.00,
        #                    "loan_series": Strategy2.objects.get(strategy_id=result.strategy_id).installment_count if result.strategy_id!=0 else 1,
        #                    "received_loan_series": installment.installment_number,
        #                    # "received_service": apply.repayment.apply_amount/100.0,
        #                    "received_service": installment.repay_fee/100.00,
        #                    "over_due_days": installment.overdue_days,
        #                    "received_over_due_pay": installment.repay_overdue_interest/100.00,
        #                    "received_over_due_fine": installment.repay_penalty/100.00 if installment.repay_penalty else 0,
        #                    "received_break_fine": 0,
        #                    "received_amount": installment.real_repay_amount/100.00,
        #                    # "operation": operation_url
        #                }
        #                data_set.append(data)
        #            if advance_set.count() > 0:
        #                print 'fdfdsfdsafdasf'
        #                advance_amount = 0
        #                installment = advance_set[0]
        #                for n in advance_set:
        #                    advance_amount = advance_amount +  Repayinstallmentrecord.objects.get(installment_id=n.id).exact_amount
        #                data = {
        #                        "id":result.id,
        #                        "username": user.name,
        #                        "idcard": user.id_no,
        #                        "received_data": installment.real_repay_time.strftime("%Y-%m-%d"),
        #                        "amount":  result.repayment.apply_amount/100.00,
        #                        "loan_series": Strategy2.objects.get(strategy_id=result.strategy_id).installment_count if result.strategy_id!=0 else 1,
        #                        "received_loan_series": installment.installment_number,
        #                        "received_service": installment.repay_fee/100.00,
        #                        "over_due_days": installment.overdue_days,
        #                        "received_over_due_pay": installment.repay_overdue_interest,
        #                        "received_over_due_fine": installment.repay_penalty/100.00 if installment.repay_penalty else 0,
        #                        "received_break_fine": advance_amount/100.00,
        #                        "received_amount": installment.real_repay_amount/100.00,
        #                    }
        #                data_set.append(data)
        #return data_set



request_result = None

def get_receivables_datatable(request):
    try:
        request_result = ReceivablesProvider().get_datatable(request)
        return request_result
    except Exception as e:
        traceback.print_exc()


def get_received_datatable(request):
    return ReceivedProvider().get_datatable(request)

def get_check_datatable(request):
    return CheckApplyProvider().get_datatable(request)



def get_receivables_columns():
    return ReceivablesProvider().get_columns()

def get_received_columns():
    return ReceivedProvider().get_columns()

def get_check_columns():
    return CheckApplyProvider().get_columns()
