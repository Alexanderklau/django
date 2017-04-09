# -*- coding: utf-8 -*-
import json
from django.db.models import Q,F, Count, Sum
from business_manager.order.apply_models import Apply,ExtraApply
from business_manager.order.models import Chsi,Profile,User
from business_manager.strategy.models import Strategy2
from business_manager.review.models import Review, ReviewRecord, CollectionRecord, BankStatement
from business_manager.employee.models import Employee, EmployeeGroup, get_employee_platform
from business_manager.collection.models import *
from business_manager.util.data_provider import DataProvider
from business_manager.python_common.log_client import CommonLog as Log
from business_manager.util.tkdate import *
from business_manager.collection.strategy import Strategy
from datetime import timedelta,datetime

from django.views.decorators.csrf import csrf_exempt
from numpy import pv

from business_manager.util.common_response import ImportResponse
from business_manager.custom_command.management.commands import base_dispatch

global_time_range = [[], [0,5],[5,15],[15,30],[30,60],[60,999999]]
global_show_th = {
     1:["信托","信托"],
     6:["信托","信托"],
     5:["信托","信托"],
     12:["信托","信托"],
     10:["0.00%","0.30%"],
     11:["0.00%","0.30%"],
     15:["1.67%","4.00%"],
}
global_show = {
     1:["信托","0"],
     6:["信托","0"],
     5:["信托","0"],
     12:["信托","0"],
     10:["0.00%","0.003"],
     11:["0.00%","0.003"],
     15:["1.67%","0.4"],
}
def get_card_id_from_apply(apply):
    return apply.create_by.id_no

class PayLoanDataProvider(DataProvider):
    def object_filter(self, request):
        repay_list = []
        # query_type =request.GET.get("query_type")
        # query_str=request.GET.get("query_str")
        # if query_type != 'none' and query_str:
            # if query_type == 'id':
                # user_list = User.objects.filter(Q(id_no=query_str))
            # if query_type == 'name':
                # user_list = User.objects.filter(Q(name__icontains=query_str))
            # if query_type == 'phone':
                # user_list = User.objects.filter(Q(phone_no=query_str))
            # if query_type == 'phone' or query_type == 'name' or query_type == 'id':
                # for user in user_list:
                    # for repay in  RepaymentInfo.objects.filter(user= user):
                        # repay_list.append(repay)
            # if query_type == 'order':
                # for repay in RepaymentInfo.objects.filter(order_number = query_str):
                    # repay_list.append(repay)

        stime = get_today()
        etime = get_tomorrow()
        timerange =request.GET.get("time")
        if timerange == "today" :
            stime = get_today()
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
        elif timerange == "all" :
            stime = get_tomorrow() - timedelta(1000)
            etime = get_tomorrow() + timedelta(1000)
        else:
            stime = request.GET.get("stime")
            etime = request.GET.get("etime")
        query_time = Q(create_at__lt = etime, create_at__gt = stime)
        status =request.GET.get("status")
        s = Apply.WAIT
        if status == "waiting" :
            s = Apply.WAIT
        elif status == "prepayed" :
            s = Apply.WAIT_MONEY
        elif status == "success" :
            s = Apply.PAY_SUCCESS
        elif status == "failed" :
            s = Apply.PAY_FAILED
        elif status == "mifan_failed" :
            s = Apply.SEND_MIFAN_FAIL
        else:
            s = 'all'
       # 没有 米饭 的逻辑了.
       #如果是米饭status 确认到款请求的 status 默认就是1
        #if request.GET.get("mifan") == "mifan_status":
        #    s = '1'
       #如果是米饭请求的 status 默认就是0
        # if request.GET.get("mifan") == "mifan":
            # s = Apply.WAIT
        #添加上面查询条件对应的repayment约束
        query_status = None
        #if s == 'all':
        #    query_status = Q(type = 'l') & ~Q(repayment_id = None) &   Q(order_number_in = repay_list)
        #else:
        #    query_status = Q(type = 'l', status = s) & ~Q(repayment_id = None)  & Q(order_number_in = repay_list)
        if s == 'all':
            query_status = Q(type = 'l') & ~Q(repayment_id = None)
            # 没有 米饭 的逻辑了.
            # if request.GET.get("mifan") == "mifan" or request.GET.get("mifan") == "mifan_status":
                # query_status = Q(type = 'l', status__in =  [Apply.ASK_MONEY, Apply.SEND_MIFAN_FAIL] ) & ~Q(repayment_id = None)
            # else:
                # query_status = Q(type = 'l') & ~Q(repayment_id = None)
        else:
            query_status = Q(type = 'l', status = s) & ~Q(repayment_id = None)

        channel = request.GET.get("channel")
        # c = None
        c = RepaymentInfo.MIFAN

       # 没有 米饭 的逻辑了.
        # if channel == "mifan" :
            # c = RepaymentInfo.MIFAN
        # elif channel == "xintuo" :
            # c = RepaymentInfo.XINTUO
        # else :
            # Log().error("unknown channel %s" % channel)
        query_channel = Q(repayment__capital_channel_id = c)
        query_strategy_type =request.GET.get("query_strategy_type")
        query_strategy = Q(repayment__strategy_id = int(query_strategy_type))
        if query_strategy_type == '0':
            apply_list_filter = Apply.objects.filter(query_time & query_status & query_channel ).order_by("-id")
        else:
            apply_list_filter = Apply.objects.filter(query_time & query_status & query_channel &query_strategy).order_by("-id")

        print query_time
        print query_status
        print query_channel

        print apply_list_filter.count()
        return apply_list_filter

        # try:
            # # apply_list_query = Apply.objects.filter(repayment__in = repay_list)
        # except Exception,e:
            # Log().error("access mysql occur a exception:  except:  %s" % str(e))
        # if query_type == 'none' or not query_type:
            # return apply_list_query | apply_list_filter
        # else:
            # return apply_list_query & apply_list_filter


    def get_columns(self):
        return [u"申请ID", u"用户id", u"订单号", u"用户",u"身份证", u"资金渠道", u"借款金额",
                # u"到账金额", u"借贷方式", u"申请时间", u"起息日", u"状态", u"银行"]
                u"到账金额", u"借贷方式", u"申请时间", u"起息日", u"状态", u"米饭打款状态",u"银行"]

    def get_query(self):
        return ["create_by__id__iexact", "create_by__name__icontains", "create_by__phone_no__iexact", "create_by__id_no__iexact", "repayment__order_number"]

    def fill_data(self, query_set):
        print 'in fill_data'
        print query_set
        data_set = []
        for result in query_set.values():
            apply = Apply.objects.get(pk = result["id"])
            repay = RepaymentInfo.objects.get(pk = result["repayment_id"])
            try:
                #ea = ExtraApply.objects.get(apply_id= 3501)
                ea = ExtraApply.objects.get(apply_id=apply.id)
                mifan = ea.message_2
            except ExtraApply.DoesNotExist:
                mifan = ""
                #print mifan
                #print "excp", e
                #traceback.print_exc()
            data = {"id": apply.id,
                    "uid": repay.user.id,
                    "order_number": apply.repayment.order_number,
                    "name": repay.user.name,
                    "card_id": get_card_id_from_apply(apply),
                    "channel": repay.get_capital_channel_id_display(),
                    "amount": repay.apply_amount/100.0,
                    "repay_amount": repay.exact_amount/100.0,
                    "strategy": repay.get_strategy_id_display(),
                    #repay.bank_card.get_bank_type_display(),
                    "apply_time": repay.apply_time.strftime("%Y-%m-%d %H:%M:%S") if repay.apply_time else "",
                    "getpay_time": repay.first_repay_day.strftime("%Y-%m-%d %H:%M:%S") if repay.first_repay_day else "",
                    "status": apply.get_status_display(),
                    "mifan_status": mifan,
                    "bank_type": repay.bank_card.get_bank_type_display(),
                    "DT_RowId": apply.id
                    }
            data_set.append(data)
        return data_set

class RepayLoanDataProvider(DataProvider):
    def object_filter(self, request):
        channel = request.GET.get("channel")
        c = None
        if channel == "mifan":
            c = 2
        elif channel == "xintuo":
            c = 1
        # else:
            # Log().error("unknown channel %s" % channel)
        query_channel = Q(repayment__capital_channel_id = c) if c else Q()

        stime = get_today()
        etime = get_tomorrow()
        timerange =request.GET.get("time")
        if timerange == "today" :
            stime = get_today()
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
        elif timerange == "all" :
            stime = get_today() - timedelta(1000)
            etime = get_today() + timedelta(5000)
        else:
            stime = request.GET.get("stime")
            etime = request.GET.get("etime")
        query_time = Q(create_at__lt = etime, create_at__gt = stime)

        #status =request.GET.get("status")
        #s = '0'
        #if status == "waiting" :
        #    s = '0'
        #elif status == "prepayed" :
        #    s = '1'
        #elif status == "success" :
        #    s = '2'
        #elif status == "failed" :
        #    s = '3'
        #else:
        #    s = 'all'
        #if s == 'all':
        #    apply_list = Apply.objects.filter(Q(create_at__lt = etime, create_at__gt = stime, type = 'p'))
        #else:
        #    apply_list = Apply.objects.filter(Q(create_at__lt = etime, create_at__gt = stime, type = 'p', status = s))
        #repay_list = RepaymentInfo.objects.filter(Q(apply__in = apply_list))

        query_status = None
        status =request.GET.get("status")
        if status == "wait_repay" :
            query_status = Q(status = '0')
        elif status == "repay_success" :
            query_status = Q(status = '9')
        elif status == "repay_failed" :
            query_status = Q(status = 'c')
        elif status == "repay_error" :
            query_status = Q(status = 'o')
        elif status == "part_success" :
            query_status = Q(status = 'd')
        elif status == "wait_check" :
            query_status = Q(status = 'k')
        elif status == "processing" :
            query_status = Q(status = 'i')
        elif status == "all" :
            query_status = Q()
        else :
            query_status = Q()

        if request.GET.get("query_status_type") == "batch_repay" and status == "all" :
            query_status = Q(status = '0') | Q(status = 'd') | Q(status = 'c') | Q(status = 'i')
        querytype = Q(type = 'p')

        repay_list = []
        query_type =request.GET.get("query_type")
        query_str=request.GET.get("query_str")
        if query_type != 'none' and query_str:
            if query_type == 'id':
                user_list = User.objects.filter(Q(id_no=query_str))
            if query_type == 'name':
                user_list = User.objects.filter(Q(name__icontains=query_str))
            if query_type == 'phone':
                user_list = User.objects.filter(Q(phone_no=query_str))
            if query_type == 'phone' or query_type == 'name' or query_type == 'id':
                #print user_list
                for user in user_list:
                    #print user
                    for repay in  RepaymentInfo.objects.filter(user= user):
                        repay_list.append(repay)
            if query_type == 'order' and query_str:
                for repay in RepaymentInfo.objects.filter(order_number = query_str):
                    repay_list.append(repay)

        print 'object_filter:'
        query_strategy_type =request.GET.get("query_strategy_type")
        query_strategy = Q(repayment__strategy_id = int(query_strategy_type))
        print query_time & query_status & querytype & query_strategy & query_channel
        if query_strategy_type == '0':
             apply_list_filter = Apply.objects.filter(query_time & query_status & querytype & query_channel)
        else:
             apply_list_filter = Apply.objects.filter(query_time & query_status & querytype & query_strategy & query_channel)
        #print apply_list_filter.count()
        apply_list_query = Apply.objects.filter(repayment__in = repay_list)
        print apply_list_query
        print apply_list_filter
        if query_type == 'none' or not query_type:
            return apply_list_query | apply_list_filter
        else:
            return apply_list_query & apply_list_filter


    def get_columns(self):
        return [u"订单ID", u"订单号", u"用户名字",u"身份证", u"借款金额", u"到账金额", u"借贷方式", u"银行名称", u"申请时间", u"起息日", u"状态",u"当前期数"]
        # return [u"订单ID", u"订单号", u"用户名字",u"身份证", u"借款金额", u"到账金额", u"借贷方式", u"银行名称", u"申请时间", u"起息日", u"状态"]

    def get_query(self):
        return ["create_by__id__iexact", "create_by__name__icontains", "create_by__phone_no__iexact", "create_by__id_no__iexact", "repayment__order_number"]

    def get_should_repay_periods(self, apply):
        peroids = []
        zero_installment = InstallmentDetailInfo.objects.filter(repayment=apply.repayment, installment_number=0, repay_status__in=[1, 2]).first()
        if zero_installment:
            peroids.append(zero_installment.installment_number)

        #number = apply.money + 1
        #installments = InstallmentDetailInfo.objects.filter( Q(repayment=apply.repayment) & Q( installment_number__gte =  number))
        installments = InstallmentDetailInfo.objects.filter( Q(repayment=apply.repayment) & Q( installment_number__gte =  (apply.money + 1 )))

        for i in installments:
            if i.repay_status == 3 or i.repay_status == 8:
                #continue
                peroids.append(i.installment_number)
            elif i.repay_status == 7:
                break
            else:
                peroids.append(i.installment_number)
        return peroids



    def fill_data(self, query_set):
        data_set = []
        for result in query_set.values():
            apply = Apply.objects.get(pk = result["id"])
            repay = RepaymentInfo.objects.get(pk = result["repayment_id"])
            _strategy = Strategy.objects.get(pk=repay.strategy_id)
            installments = InstallmentDetailInfo.objects.filter(Q(repayment=apply.repayment) &  Q(installment_number__in = self.get_should_repay_periods(apply)))
            current_peroids = 0
            if installments.first() and installments.first().installment_number > 0:
                if apply.status in [3, 8, 9, '3', '8', '9']:
                    current_peroids = apply.money + 1
                else:
                    current_peroids = installments.first().installment_number + installments.count() - 1

            first_ins = InstallmentDetailInfo.objects.filter(repayment=apply.repayment).first()
            getpay_time = ""
            if first_ins:
                getpay_time = first_ins.should_repay_time
            data = {
                    "id": repay.user.id,
                    "order_number": apply.repayment.order_number,
                    "name": repay.user.name,
                    "card_id": get_card_id_from_apply(apply),
                    "amount": repay.apply_amount/100.0,
                    "repay_amount": repay.exact_amount/100.0,
                    # "strategy": repay.get_strategy_id_display(),
                    "strategy": _strategy.description,
                    "bank_data": repay.bank_card.bank_name,
                    "apply_time": repay.apply_time.strftime("%Y-%m-%d %H:%M:%S") if repay.apply_time else "",
                    "getpay_time": getpay_time.strftime("%Y-%m-%d %H:%M:%S") if getpay_time else "",
                    "status":apply.get_status_display(),
                    # "current_peroids": apply.money + 1 if InstallmentDetailInfo.objects.filter().first().in else 0,
                    # "current_peroids": installments.first().installment_number + installments.count() - 1 if installments.first() and installments.first().installment_number > 0 else 0,
                    "current_peroids": current_peroids,

                    "DT_RowId": apply.id
                    }
            # print 'sdfasdfadsf 123123'
            # print apply.type
            # print apply.status
            if apply.type in ['p'] and apply.status in ['0']:
                if BankStatement.objects.filter(bankcard=apply.repayment.bank_card, status=1).first():
                    data['status'] = "预扣款审核中"
                else:
                    data['status'] = "等待扣款"

            data_set.append(data)
        return data_set

def get_over_due_days(install):
    return install.overdue_days
#def get_over_due_days(install):
#    if install.real_repay_time == None:
#        #return "错误还款时间"
#        today  = datetime.now()
#        return (datetime.combine(today, datetime.min.time()) - datetime.combine(install.should_repay_time, datetime.min.time())).days
#    if install.repay_status == 2:
#        today  = datetime.now()
#        return (datetime.combine(today, datetime.min.time()) - datetime.combine(install.should_repay_time, datetime.min.time())).days
#    elif install.repay_status == 7  or install.repay_status == 3:
#        return 0
#    elif install.repay_status == 1:
#        return 1
#    elif install.repay_status == 8:
#        return (datetime.combine(install.real_repay_time, datetime.min.time()) - datetime.combine(install.should_repay_time, datetime.min.time())).days
#    else:
#        return (datetime.combine(install.real_repay_time, datetime.min.time()) - datetime.should_repay_time.combine(install.should_repay_time, datetime.min.time())).days
#
#def get_over_due_days(install):
#    if install.real_repay_time == None:
#        #return "错误还款时间"
#        today  = datetime.now()
#        return (datetime.combine(today, datetime.min.time()) - datetime.combine(install.should_repay_time, datetime.min.time())).days
#    if install.repay_status == 2:
#        today  = datetime.now()
#        return (datetime.combine(today, datetime.min.time()) - datetime.combine(install.should_repay_time, datetime.min.time())).days
#    elif install.repay_status == 7  or install.repay_status == 3:
#        return 0
#    elif install.repay_status == 1:
#        return 0
#    elif install.repay_status == 8:
#        return (datetime.combine(install.real_repay_time, datetime.min.time()) - datetime.combine(install.should_repay_time, datetime.min.time())).days
#    else:
#        return (datetime.combine(install.real_repay_time, datetime.min.time()) - datetime.should_repay_time.combine(install.should_repay_time, datetime.min.time())).days
#

def get_real_repay_amount(repay):
    i = 0
    installs = InstallmentDetailInfo.objects.filter(Q(repayment__id = repay.id))
    for item in installs:
        if item.should_repay_time > datetime.now():
           continue
        else:
           if item.repay_status != 2:
              i = i+item.real_repay_amount
    return i/100.0

def get_over_due_amount(repay):
    i = 0
    installs = InstallmentDetailInfo.objects.filter(Q(repayment__id = repay.id))
    for item in installs:
        if item.should_repay_time > datetime.now():
           continue
        else:
           if item.repay_status == 2 or  item.repay_status == 8:
              i = i+(item.should_repay_amount -item.real_repay_amount)
    return i/100.0


    """计算还钱跨越的期数"""
def get_installment_numbers4repayrecord(repayrecord):
    ret_str = ""
    installRecords = Repayinstallmentrecord.objects.filter(Q(repay_record = repayrecord))
    for i in installRecords:
        ret_str = ret_str + str(i.installment.installment_number)
    return ret_str
    """计算还钱方式种类"""
def get_record_repay_type(repayrecord):
    show_type = {
         1:["银联"],
         3:["支付宝"],
         4:["对公"]
    }
    return show_type[repayrecord.repay_channel]

def get_installment_repay_type_count(install):
    show_type = {
         1:u"银联",
         3:u"支付宝",
         4:u"对公"
    }
    installRecords = Repayinstallmentrecord.objects.filter(Q(installment = install))
    repayRecords_type = set()
    for i in installRecords:
        repayRecords_type.add(i.repay_channel)
    assert len(repayRecords_type) >= 0
    ret_str = ""
    for e in repayRecords_type:
        ret_str = ret_str + "  " + str(show_type[e])
    return ret_str
    #return len(repayRecords_type)

    """计算还钱笔数 这个以payrecord为口径 应该没误差"""
def get_repayrecord_repay_count(repayrecord):
    #repayRecords.add(i.repay_record)
    if repayrecord.repay_channel == 1:
        return int(repayrecord.exact_amount/100000) + 1
    else:
        return 0

    """计算还钱笔数 应该有误差"""
def get_installment_repay_count(install):
    if install.real_repay_amount > 0:
        installRecords = Repayinstallmentrecord.objects.filter(Q(installment = install))

        repayRecords = set()
        for i in installRecords:
            repayRecords.add(i.repay_record)
        count = 0
        for i in repayRecords:
        #for i in installRecords:
            #repayRecords.add(i.repay_record)
            if i.repay_channel == 1:
                if i.exact_amount == 0:
                    continue
                if i.exact_amount <= 100000:
                    count = count + 1
                else:
                    count = count + i.exact_amount/100000 + (1 if i.exact_amount%100000 > 0  else 0)
            else:
                pass
        return count
    else:
        return 0

def get_over_due_peroids(repay):
    i = 0
    installs = InstallmentDetailInfo.objects.filter(Q(repayment__id = repay.id))
    for item in installs:
        if item.should_repay_time > datetime.now():
           continue
        else:
           if item.repay_status == 2 or  item.repay_status == 8:
              i = i+1
    return i

def get_over_due_peroids_rate(repay):
    i = 0
    ii = 0
    installs = InstallmentDetailInfo.objects.filter(Q(repayment__id = repay.id))
    for item in installs:
        if item.should_repay_time > datetime.now():
           continue
        else:
           ii = ii+1
           if item.repay_status == 2 or  item.repay_status == 8:
              i = i+1
    return "%d/%d" % (i,ii)

def get_real_repay_peroids(repay):
    i = 0
    installs = InstallmentDetailInfo.objects.filter(Q(repayment__id = repay.id))
    for item in installs:
        if item.should_repay_time > datetime.now():
           continue
        else:
           if item.repay_status == 2 or  item.repay_status == 8:
              i = i+1
    return i

def get_periods_from_repayment(repay):
    if Strategy2.objects.get(strategy_id=repay.strategy_id).installment_days in (21,28):
        return 1
    else:
        return  Strategy2.objects.get(strategy_id=repay.strategy_id).installment_count

def get_numbers_from_strategy(id):
    return Strategy2.objects.get(strategy_id=id).installment_days

def get_corpus_from_repayment(repay):
    if Strategy2.objects.get(strategy_id=repay.strategy_id).installment_days in (21,28):
        return '%.2f' % ((repay.repay_amount - 200) / ( (1 + 0.00034)**get_numbers_from_strategy(repay.strategy_id) ) /100.0)
    else:
        peroids = Strategy2.objects.get(strategy_id=repay.strategy_id).installment_count
        return  '%.2f' % ( pv( (1.13 ** (1/12.0) -1), peroids,-(repay.repay_amount - 200 * peroids )/3)/100.0 )

def get_taikang_repayment(repay):
    if Strategy2.objects.get(strategy_id=repay.strategy_id).installment_days in (21,28):
        return '%.2f' % ((repay.repay_amount - 200 )/ ( (1 + 0.00034)**get_numbers_from_strategy(repay.strategy_id) ) /100.0 - (repay.apply_amount/100.0) )
    else:
        peroids = Strategy2.objects.get(strategy_id=repay.strategy_id).installment_count
        return  '%.2f' % ( pv( (1.13 ** (1/12.0) -1), peroids,-(repay.repay_amount - 200 * peroids )/3)/100.0 - (repay.apply_amount/100.0) )

def get_should_be_repayment(repay):
    if Strategy2.objects.get(strategy_id=repay.strategy_id).installment_days in (21,28):
        return '%.2f' % ((repay.repay_amount - 200 )/ 100.0)
    else:
        peroids = Strategy2.objects.get(strategy_id=repay.strategy_id).installment_count
        return  '%.2f' % ((repay.repay_amount - 200 * peroids )/3/100.0)

class FundDetailDataProvider(DataProvider):
    def object_filter(self, request):
        custom_type = request.GET.get("custom_type")
        if custom_type == 'all':
            query_custom_type = Q()
        else:
            query_custom_type = Q(user__profile__job = custom_type)
        channel = request.GET.get("channel")
        c = None
        if channel == "mifan" :
            c = 2
            query_channel = Q(capital_channel_id = c)
        elif channel == "xintuo" :
            c = 1
            query_channel = Q(capital_channel_id = c)
        else :
            query_channel = Q()


        stime = get_today()
        etime = get_tomorrow()
        timerange =request.GET.get("time")
        if timerange == "today" :
            stime = get_today()
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
        elif timerange == "all" :
            stime = get_tomorrow() - timedelta(1000)
            etime = get_tomorrow() + timedelta(1000)
        else:
            stime = request.GET.get("stime")
            etime = request.GET.get("etime")
        query_time = Q(first_repay_day__lt = etime, first_repay_day__gt = stime)

        repayments = RepaymentInfo.objects.filter(Q(repay_status__in = [0,1,2,3,5]) & query_time & query_channel & query_custom_type).order_by("id")
        #repayments = RepaymentInfo.objects.get(order_number = 370421206753848686)
        #print repayments.user.profile
        #print repayments.user.profile.job

        return repayments
    def get_query(self):
        return ["user__name__icontains",  "user__id_no__iexact"]
    def get_columns(self):
        return [u"详情下拉",u"渠道", u"合同",u"姓名",u"类型",u"身份证", u"金额", u"本金", u"期数",u"利率",u"服务费" , u"应还",u"泰康",u"放款日期"]
    def fill_data(self, query_set):
        data_set = []
        for repay in query_set:
            print "***" ,repay.strategy_id
            repay_records = list()
            records = Repayrecord.objects.filter(repayment = repay)
            for i in records:
                temp_record = dict()
                temp_record['exact_amount'] = str(i.exact_amount)
                temp_record['bank_card'] = str(i.bank_card)
                temp_record['create_at'] = str(i.create_at)
                temp_record['repay_channel'] = str(i.repay_channel)
                repay_records.append(temp_record)
            data = ["",
                    repay.get_capital_channel_id_display(),
                    repay.order_number,
                    repay.user.name,
                    Profile.objects.get(owner=repay.user).get_job_display(),
                    repay.user.id_no,
                    repay.apply_amount/100.0,
                    get_corpus_from_repayment(repay),
                    repay.get_strategy_id_display(),
                    global_show_th[repay.strategy_id][0],
                    str("%.2f"%(float(global_show[repay.strategy_id][1]) * repay.apply_amount/100.0)),
                    get_should_be_repayment(repay),
                    get_taikang_repayment(repay),
                    repay.first_repay_day.strftime("%Y-%m-%d"),
                    {"repay_records":repay_records}]
            data_set.append(data)
        return data_set
class RepayRecordProvider(DataProvider):
    def object_filter(self, request):
        stime = get_today()
        etime = get_tomorrow()
        timerange =request.GET.get("time")
        if timerange == "today" :
            stime = get_today()
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
        elif timerange == "all" :
            stime = get_tomorrow() - timedelta(1000)
            etime = get_tomorrow() + timedelta(1000)
        else:
            stime = request.GET.get("stime")
            etime = request.GET.get("etime")
        query_time = Q(create_at__lt = etime, create_at__gt = stime)
        repayrecords_list_filter = Repayrecord.objects.filter(query_time)
        return repayrecords_list_filter

    def get_query(self):
        return ["repayment__user__name__icontains",  "repayment__user__id_no__iexact"]

    def get_columns(self):
        return [u"详情下拉",u"订单号",u"姓名", u"id",u"身份证号", u"还款期数",u"实还金额", u"代扣笔数",u"到账金额",u"手续费",u"还款方式",u"实还日期"]

    def fill_data(self, query_set):
        show_type = {
             1:["银联"],
             3:["支付宝"],
             4:["对公"]
        }
        data_set = []
        for result in query_set.values():
            record = Repayrecord.objects.get(pk = result["id"])
            repayment = record.repayment
            installmentrecords = Repayinstallmentrecord.objects.filter(repay_record = record)
            install_rerpay_records  = list()
            for i in installmentrecords:
                temp_record = dict()
                temp_record['exact_amount'] = i.exact_amount
                temp_record['exact_principle'] = i.exact_principle
                temp_record['exact_interest'] = i.exact_interest
                temp_record['create_at'] = str(i.create_at)
                temp_record['repay_channel'] = show_type[i.repay_channel]
                temp_record['repayment'] = str(i.repayment.order_number)
                temp_record['installment'] = str(i.installment.installment_number)
                install_rerpay_records.append(temp_record)
            data = ["",
                    repayment.order_number,
                    repayment.user.name,
                    record.id,
                    repayment.user.id_no,
                    get_installment_numbers4repayrecord(record),
                    record.exact_amount/100.0,
                    get_repayrecord_repay_count(record),
                    (record.exact_amount - 100*( get_repayrecord_repay_count(record)))/100.0,
                    (2 - get_repayrecord_repay_count(record)),
                    get_record_repay_type(record),
                    str(record.create_at),
                    {"install_rerpay_records":install_rerpay_records}]
        #    data = ["order_no":record.id,
        #            "name":record.id,
        #            "id":record.id,
        #            "card_id":record.id,
        #            "ammount":record.id,
        #            "periods":record.id,
        #            "exact_amount":record.id,
        #            "bank_fee_count":record.id,
        #            "get_exact_amount":record.id,
        #            "bank_fee":record.id,
        #            "repay_ways":record.id,
        #            "repay_time":record.id]



            data_set.append(data)
        return data_set

class OverDueProvider(DataProvider):
    def object_filter(self, request):
        custom_type = request.GET.get("custom_type")
        if custom_type == 'all':
            query_custom_type = Q()
        else:
            query_custom_type = Q(user__profile__job = custom_type)
        channel = request.GET.get("channel")
        c = None
        if channel == "mifan" :
            c = 2
            query_channel = Q(capital_channel_id = c)
        elif channel == "xintuo" :
            c = 1
            query_channel = Q(capital_channel_id = c)
        else :
            query_channel = Q()


        over_due_type = request.GET.get("over_due_type")
        if over_due_type == 'all':
            query_base= Q(repay_status__in = [2,8])
        elif over_due_type == 'already':
            query_base= Q(repay_status = 8)
        else:
            query_base= Q(repay_status = 2)


        over_due_time_range = request.GET.get("over_due_time_range")
        #if over_due_time_range == time_range
        #query_time_range= Q()
        #repayments = RepaymentInfo.objects.filter(query_base & query_channel & query_custom_type & query_time_range).order_by("id")
        repayments = RepaymentInfo.objects.filter(query_base & query_channel & query_custom_type ).order_by("id")
        return repayments

    def get_columns(self):
        return [u"期数", u"订单号", u"渠道", u"类型", u"借款金额", u"应还日期", u"应还笔数",
                u"应还金额", u"实还笔数", u"实还金额", u"逾期笔数", u"逾期金额", u"逾期率"]

    def fill_data(self, query_set):
        data_set = []
        for repay in query_set:
            data = [repay.get_strategy_id_display(),
                    repay.order_number,
                    repay.get_capital_channel_id_display(),
                    Profile.objects.get(owner=repay.user).get_job_display(),
                    repay.apply_amount/100.0,
                    str(repay.first_repay_day),
                    get_periods_from_repayment(repay),
                    repay.repay_amount/100.0,
                    get_real_repay_peroids(repay),
                    get_real_repay_amount(repay),
                    get_over_due_peroids(repay),
                    get_over_due_amount(repay),
                    get_over_due_peroids_rate(repay)]
            data_set.append(data)
        return data_set

class OverDueDetailProvider(DataProvider):
    def object_filter(self, request):
        #repayments = RepaymentInfo.objects.filter(query_base ).order_by("id")

        over_due_type = request.GET.get("over_due_type")
        #print over_due_type

        if over_due_type == 'yet_already':
            query_base= Q(repay_status__in = [2,8])
        elif over_due_type == 'already':
            query_base= Q(repay_status = 8)
        elif over_due_type == 'yet':
            query_base= Q(repay_status = 2)
        elif over_due_type == 'normal':
            query_base= Q(repay_status = 3)
        else:
            query_base= Q()


        timerange =request.GET.get("time")
        if timerange == "all":
            query_time = Q()
        else:
            stime = request.GET.get("stime")
            etime = request.GET.get("etime")
            s = datetime.strptime(stime,'%Y-%m-%d %H:%M:%S')
            e = datetime.strptime(etime,'%Y-%m-%d %H:%M:%S')
            query_time =Q(should_repay_time__lt = e ) &  Q(should_repay_time__gte = s )


        custom_type = request.GET.get("custom_type")
        if custom_type == 'all':
            query_custom_type = Q()
        else:
            query_custom_type = Q(repayment__user__profile__job = custom_type)
        channel = request.GET.get("channel")
        c = None
        if channel == "mifan" :
            c = 2
            query_channel = Q(repayment__capital_channel_id = c)
        elif channel == "xintuo" :
            c = 1
            query_channel = Q(repayment__capital_channel_id = c)
        else :
            query_channel = Q()
        query_repay_status =  Q(repayment__repay_status__in = [1,2,3,8])
        Installs = InstallmentDetailInfo.objects.filter( query_channel & query_custom_type & query_time & query_base & query_repay_status)
        #print Installs.query, Installs.count()

        over_due_time_range= request.GET.get("over_due_time_range")
        if over_due_time_range == 'all':
            #Installs = InstallmentDetailInfo.objects.filter(Q(should_repay_amount__gt= F('real_repay_amount'))).order_by("id")
            return Installs
        else:
            return_set = []
            for install in Installs:
                i = get_over_due_days(install)
                #print "hah", i
                #print global_time_range[int(over_due_time_range)][0]
                #print global_time_range[int(over_due_time_range)][0]
                if i > global_time_range[int(over_due_time_range)][0] and i < global_time_range[int(over_due_time_range)][1]:
                    return_set.append(install.id)
                else:
                    pass
            return InstallmentDetailInfo.objects.filter(id__in = return_set)

    def get_query(self):
        return ["repayment__user__id__iexact", "repayment__user__name__icontains", "repayment__user__phone_no__iexact", "repayment__user__id_no__iexact", "repayment__order_number"]

    def get_columns(self):
        return [u"渠道",u"订单号",u"姓名",u"类型",u"身份证", u"借款金额", u"期数",u"还款期数",u"应还日期", u"每期应还",  u"逾期天数",u"滞纳金", u"实还金额",u"逾期状态",u"实还日期"]
        #return [u"渠道", u"合同号",u"姓名",u"类型",u"身份证", u"借款金额", u"期数",u"还款期数",u"应还日期", u"每期应还",  u"逾期天数",u"滞纳金", u"实还金额",u"逾期状态"]

    def fill_data(self, query_set):
        data_set = []
        for install in query_set:
            repay = install.repayment
            data = [repay.get_capital_channel_id_display(),
                    repay.order_number,
                    repay.user.name,
                    Profile.objects.get(owner=repay.user).get_job_display(),
                    repay.user.id_no,
                    repay.apply_amount/100.0,
                    get_periods_from_repayment(repay),
                    install.installment_number,
                    str(install.should_repay_time),
                    install.should_repay_amount/100.0,
                    get_over_due_days(install),
                    install.repay_overdue/100.0,
                    install.real_repay_amount/100.0,
                    install.get_repay_status_display(),
                    str(install.real_repay_time)]
            data_set.append(data)
        return data_set

class OverDueDetail_sum_Provider(OverDueDetailProvider):
    def get_columns(self):
        return [u"时间段",u"逾期笔数",u"正常笔数",u"总笔数",u"逾期金额",u"正常金额",u"总金额",u"逾期比率"]


def get_pay_loan_datatable(request):
    return PayLoanDataProvider().get_datatable(request)

def get_repay_loan_datatable(request):
    return RepayLoanDataProvider().get_datatable(request)

def get_pay_loan_columns():
    return PayLoanDataProvider().get_columns()

def get_repay_loan_columns():
    return RepayLoanDataProvider().get_columns()

def get_table1_datatable(request):
    return FundDetailDataProvider().get_datatable(request)

def get_table1_columns():
    return FundDetailDataProvider().get_columns()

def get_table2_datatable(request):
    return OverDueProvider().get_datatable(request)

def get_table2_columns():
    return OverDueProvider().get_columns()

def get_table3_datatable(request):
    return OverDueDetailProvider().get_datatable(request)

def get_table3_columns():
    return OverDueDetailProvider().get_columns()

def get_table4_datatable(request):
    return RepayRecordProvider().get_datatable(request)

def get_table4_columns():
    return RepayRecordProvider().get_columns()


def get_table3_result_datatable(request):
    query_set = OverDueDetail_sum_Provider().object_filter(request)
    #print query_set.count()
    timerange =request.GET.get("time")
    if timerange == "all":
        query_time = "所有时间段"
    else:
        stime = request.GET.get("stime")[:10]
	etime = request.GET.get("etime")[:10]
        query_time  = "form:" + stime + "to" + etime
    normal = 0
    normal_amount = 0
    over_due = 0
    over_due_amount = 0
    installs_sum = 0
    installs_sum_amount  = 0
    for install in query_set:
        installs_sum = installs_sum + 1
        installs_sum_amount = installs_sum_amount + install.should_repay_amount
        if install.repay_status == 2 or install.repay_status == 8:
            over_due_amount = over_due_amount + install.should_repay_amount
            over_due = over_due + 1
        else:
            normal = normal + 1
            normal_amount = normal_amount + install.should_repay_amount
    #[u"时间段",u"逾期笔数",u"正常笔数",u"总笔数",u"逾期金额",u"正常金额",u"总金额",u"逾期比率"]
    normal_amount = normal_amount/100.0
    over_due_amount = over_due_amount/100.0
    installs_sum_amount = installs_sum_amount/100.0
    if installs_sum_amount == 0.0:
        result = [query_time,  over_due,normal,installs_sum,over_due_amount,normal_amount,installs_sum_amount,0]
    else:
        result = [query_time,  over_due,normal,installs_sum,over_due_amount,normal_amount,installs_sum_amount,over_due_amount/installs_sum_amount]
    #result = {"qury_time":qury_time, "normal":normal, "normal_amount":normal_amount,"over_due":over_due,"over_due_amount":over_due_amount ,"install_sum":install_sum,"installs_sum_amount":installs_sum_amount}
    return result

def get_table3_result_columns():
    return OverDueDetail_sum_Provider().get_columns()



collection_groups = {
    "a": "M0",
    "b": "M1",
    "c": "M2",
    "d": "M3",
    "e": "M4",
    "g": "M5",
    "h": "M5+"
}
def dispatch_button(request):
    if request.method != 'GET':
        return ImportResponse.failed(msg=u'错误方法')
    from business_manager.collection.views import CollectionDataProvider
    # 过滤订单， 只要未分配、未受理、已受理 为了兼容加了老状态
    applies = CollectionDataProvider().object_filter(request).filter(status__in=(Apply.WAIT, Apply.PROCESSING, Apply.COLLECTION, Apply.WAIT_DISTRIBUTION, Apply.NOT_ACCEPT, Apply.APPLY_PROCESSING))
    # apply_info = applies.values('type').annotate(apply_count=Count('id')).annotate(money_sum=Sum('rest_repay_money'))
    ret = []
    command = base_dispatch.Command()
    # limit quantity of order (< 500)
    # tmp_count = applies.count()
    # if tmp_count > 500:
    #     return ImportResponse.failed(msg=u'订单数量太多, 当前数量：{}'.format(tmp_count))
    for info in collection_groups:
        apply_ids = applies.filter(type=info)
        if not apply_ids:
            continue
        ret_app = []
        app_id = []

        # 为了保证和分配后的结果保持一致加了for
        # 下面这个for是卡的根源。。。
        for apply in apply_ids:
            install = command.check_installment_by_apply(apply)
            if install:
                ret_app.append(apply)
                app_id.append(apply.id)
        if not ret_app:
            continue
        ret.append({
            "collection_type": collection_groups.get(info, 'M1'),
            "total_money": sum([item.rest_repay_money for item in ret_app]),  # 总金额
            "apply_count": len(ret_app),  # 总户数
            "apply_id_list": app_id
        })
    # print ret
    ret.sort(key=lambda item: int(item['collection_type'][1]))
    return ImportResponse.success(data=ret)


@csrf_exempt
def hand_dispatch(request):
    """
    订单手动分配
    :param request:
    :return:
    """
    # import pdb;pdb.set_trace()
    if request.method != 'POST':
        return ImportResponse.failed(msg=u'错误方法')
    platform = get_employee_platform(request)[0].name
    user = request.user
    # check user permission
    employee = Employee.objects.filter(user=user).first()
    if not user.is_authenticated() or not user.is_active or not employee:
        return ImportResponse.failed(msg=u'没有权限')
    if not employee.check_page_permission(request.path):
        return ImportResponse.failed(msg=u'没有权限')
    try:
        data = json.loads(request.body)
    except:
        return ImportResponse.failed(msg=u"参数错误")
    order_id_list = data.get('apply_id_list')
    collector_id_list = data.get('collector_id_list')
    employee_group_list = data.get('collector_group_id_list')
    if not any([order_id_list, collector_id_list, employee_group_list]):
        # none params
        return ImportResponse.failed(msg=u"输入参数错误")
    collector_ids = [item['id'] for item in collector_id_list]
    collectors = Employee.objects.filter(id__in=collector_ids, user__is_active=True)
    employee_groups = EmployeeGroup.objects.filter(id__in=employee_group_list)
    # import pdb; pdb.set_trace()
    groups_collectors = Employee.objects.filter(group_list=employee_groups, user__is_active=True)
    orders = Apply.objects.filter(id__in=order_id_list, status__in=(Apply.WAIT, Apply.PROCESSING, Apply.COLLECTION, Apply.WAIT_DISTRIBUTION, Apply.NOT_ACCEPT, Apply.APPLY_PROCESSING))
    if not orders:
        # none orders
        return ImportResponse.failed(msg=u"可分配订单为空")
    dispatch_collectors = list(set(collectors) | set(groups_collectors))
    print '----1', dispatch_collectors
    if not dispatch_collectors:
        # none collectors
        return ImportResponse.failed(msg=u"没有催收员")
    dispatch_collectors = Employee.dive_collector(dispatch_collectors, collector_id_list, platform)
    print '----2', dispatch_collectors
    dispatch_orders = Apply.dive_orders(orders)
    # import pdb; pdb.set_trace()
    # 按M级别分催收员和订单
    # call dispatch scala
    ret = []
    for collect_type, orders in dispatch_orders.iteritems():
        print "----", collect_type
        collector = dispatch_collectors.get(collect_type)
        apply_count = len(orders)
        money_sum = sum([item.rest_repay_money for item in orders])
        if not orders:
            fail_msg = u'{} 没有订单。 '.format(collect_type)
            ret.append(
                {
                    "collection_type": collect_type,
                    "apply_count": apply_count,
                    "ret": 1,
                    "total_money": money_sum,
                    "ret_msg": fail_msg
                }
            )
            continue
        if not collector:
            fail_msg = u'{} 没有催收员。 '.format(collect_type)
            ret.append(
                {
                    "collection_type": collect_type,
                    "apply_count": apply_count,
                    "ret": 1,
                    "total_money": money_sum,
                    "ret_msg": fail_msg
                }
            )
            continue
        orders = list(orders)
        collector = list(collector)
        command = base_dispatch.Command()
        dispatch_ret = command.dispatch(assign_collector=collector, assign_apply=orders)
        if not dispatch_ret:
            ret.append(
                {
                    "collection_type": collect_type,
                    "apply_count": apply_count,
                    "ret": 1,
                    "total_money": money_sum,
                    "ret_msg": u'分配失败'
                }
            )
            continue
        command.dispatch_save(dispatch_ret)
        apply_count = sum([len(v['apply_id_list']) for k, v in dispatch_ret.iteritems()])
        money_sum = sum([v['amount'] for k, v in dispatch_ret.iteritems()])
        success_collector = []
        for item in dispatch_ret.values():
            if item['apply_id_list']:
                success_collector.append(item['collector'])
        collector_info = ', '.join([item.username for item in success_collector])
        success_msg = u'成功分配给{}。'.format(collector_info)
        ret.append(
            {
                "collection_type": collect_type,
                "apply_count": apply_count,
                "ret": 0,
                "total_money": money_sum,
                "ret_msg": success_msg
            }
        )
    return ImportResponse.success(data=ret)


if __name__ == "__main__":
    print "test:"
