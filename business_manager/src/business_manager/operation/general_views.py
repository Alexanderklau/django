#-*- coding: utf-8 -*-
from django.conf import settings
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext,Template
from django.http import HttpResponse, StreamingHttpResponse, JsonResponse
from django.core.servers.basehttp import FileWrapper
from django.db.models import Q

import json, os, math, uuid
import traceback
from pyExcelerator import *
from datetime import datetime
import time
from time import sleep
from business_manager.util.permission_decorator import page_permission
from business_manager.operation import data_views
from business_manager.operation.data_views  import FundDetailDataProvider,get_corpus_from_repayment,get_table3_result_datatable,OverDueDetail_sum_Provider,get_periods_from_repayment,get_over_due_days,PayLoanDataProvider,RepayLoanDataProvider,get_taikang_repayment,get_installment_repay_type_count,get_installment_repay_count
from business_manager.collection.models import *
from business_manager.review.models import Review, ReviewRecord, CollectionRecord, BankStatement
from business_manager.order.apply_models import Apply, ExtraApply, CheckApply
from business_manager.order.models import BankCard, ContactInfo, Chsi, CheckStatus, IdCard, Profile, AddressBook, CallRecord, User, Contract
from business_manager.strategy.models import Strategy2
from business_manager.python_common.log_client import CommonLog as Log
from django.views.decorators.csrf import csrf_exempt
from business_manager.review import message_client, bank_client, risk_client, redis_client
from business_manager.employee.models import Employee

#from report_def import report_table
from business_manager.collection.strategy import Strategy
from business_manager.util.tkdate import *
from business_manager.order.apply_models import Apply
from business_manager.employee.models import check_employee, get_collector_list, get_employee
from django.db import connection
from django.utils import timezone
#from django_cron import CronJobBase, Schedule
import logging
logging.basicConfig()
import threading
import calendar
from django.contrib.auth.decorators import login_required
from business_manager.collection.strategy import Strategy
from business_manager.collection.report import report_collection
from business_manager.collection.services import collection_extra_data

def luhn_check(num):
    ''' Number - List of reversed digits '''
    digits = [int(x) for x in reversed(str(num))]
    check_sum = sum(digits[::2]) + sum((dig//10 + dig%10) for dig in [2*el for el in digits[1::2]])
    return check_sum%10 == 0

def pre_repay_check_list(request):
    try :
        Log().info("pre repay check list start")
        bank_state = BankStatement.objects.filter(pre_order_number__isnull=False, status=1)
        data = []
        for bs in bank_state:
            user = bs.user
            bank_card = bs.bankcard
            dic = dict(
                user=user.name,
                id_no=user.id_no,
                pre_order_number=bs.pre_order_number,
                bank_name=bank_card.bank_name,
                bank_no=bank_card.card_number,
                status=bs.status,
            )
            dic = [
                user.name,
                user.id_no,
                # bs.pre_order_number,
                bank_card.bank_name,
                bank_card.card_number,
                bs.status,
            ]
            data.append(dic)
        
        data_str = "<p> 用户名, 用户id, 银行名, 银行卡号, 状态 </p>"
        with open('bb.csv', 'w') as fp:
            for i in data:
                i = [str(_i) for _i in i]
                line = ", ".join(i)
                print line
                fp.write(line + "\n")
                data_str += "<p> %s </p>" % line

        data=json.dumps(dict(data=data))
        return HttpResponse(data_str)

    except Exception, e:
        print "excp", e
        traceback.print_exc()
        return HttpResponse("error happen")


def auto_pay(request):
    try :
        Log().info("auto pay start")
        repayments_list = RepaymentInfo.objects.filter(Q(capital_channel_id = 2))
        applys= Apply.objects.filter(Q(type = 'l') & Q(status = '0') & Q(repayment_id__in = repayments_list ))
        for apply_item in applys:
            #repayments = RepaymentInfo.objects.get(Q(id = apply_item.repayment_id))
            #if repayments.capital_channel_id != 2:
            #   continue
            if apply_item.repayment.user.phone_no in mifan_block_list:
                jsondata[str(apply_item.id)] = u"内部黑名单，无法向米饭请款"
                jsondata[str(apply_item.id) + 'errorCode'] = "10000"
                Log().info("pay_loan mifan id number: %d result error code: %s and error message: %s " %(apply_item.id,  "10000",u"内部黑名单，无法向米饭请款"))
                # 持久化米饭返回结果 message_1 :errorcode , message_2: error message
                extra_apply = ExtraApply(apply = apply_item, message_1 = "1000",message_2 = u"内部黑名单，无法向米饭请款")
                extra_apply.save()
                continue
            if luhn_check(apply_item.repayment.bank_card.card_number):
                if apply_item.status == 'y' or apply_item.status == '0':
                    repayment = apply_item.repayment
                    s = Strategy.objects.get(pk = repayment.strategy_id)
                    Log().info("send to  mifan data start on id number: %d"  %(apply_item.id))
                    ret = json.loads(getdata4mifan(send2mifan(repayment,s)))
                    Log().info("send to  mifan data end   on id number: %d"  %(apply_item.id))
                    if ret["errorMsg"] == "success":
                        apply_item.status = '1'
                        apply_item.save()
                    else:
                        apply_item.status = '4'
                        apply_item.save()
                    Log().info("start Persistence result on id number: %d"  %(apply_item.id))
                    Log().info("pay_loan mifan id number: %d result error code: %s and error message: %s " %(apply_item.id,  ret["errorCode"], ret["errorMsg"]))
                    # 持久化米饭返回结果 message_1 :errorcode , message_2: error message
                    extra_apply = ExtraApply(apply = apply_item, message_1 = ret['errorCode'],message_2 = ret['errorMsg'])
                    extra_apply.save()
                    Log().info("end Persistence result on id number: %d"  %(apply_item.id))
                else:
                    pass
            else:
                apply_item.status = '4'
                apply_item.save()
                extra_apply = ExtraApply(apply = apply_item, message_1 = "银行卡校验出错,提醒用户更新银行卡信息",message_2 = "90000")
                extra_apply.save()
        return HttpResponse("auto_pay done")
    except Exception, e:
        print "excp", e
        traceback.print_exc()
        return HttpResponse("error happen")
def auto_pay_confirm(request):
    try :
        pay_time = request.GET.get("pay_time")
        pay_amount = request.GET.get("pay_amount", 0)
        if pay_amount:
            pay_amount = int(float(pay_amount) * 100)
        else:
            pay_amount = 0

        Log().info("auto pay confirm start")
        apply_list  = Apply.objects.filter(Q(type = 'l') & Q(status = '1'))
        for apply_item in apply_list:
                if apply_item.repayment.user.phone_no in mifan_block_list:
                    continue
                repayment = apply_item.repayment
                s = Strategy.objects.get(pk = repayment.strategy_id)
                ret = json.loads(getdata4mifan(send2mifan_confirm(repayment,s)))
                #mifan 无法判断到账状态，所以米饭已打款就认为打款成功 104 or 105
                if ret['errorCode'] == 104 or ret['errorCode'] == 105:
                    apply_item.status = '2'
                    apply_item.save()
                    try:
                        res = risk_client.pay_loan(repayment.order_number, pay_time, pay_amount)
                        if res.result_code  != 0:
                            ret["errorMsg"] =  ret["errorMsg"] + "没有成功调用后台，联系管理员"
                        bank_card = BankCard.get_pay_card(repayment.user)
                        repay_date = repayment.next_repay_time.strftime("%y-%m-%d")
                        if settings.MIFAN_DEBUG == False:
                            res = message_client.send_message(repayment.user.phone_no, (u"您申请的贷款已经完成打款，卡号:%s，还款日期：%s，借贷信息已提交央行征信。rst客服热线400-606-4728 " % (bank_card_card_number, repay_date)).encode("gbk"), 5)
                            Log().info("send message %s " % res)
                    except Exception, e:
                        traceback.print_exc()
                        #print res.result_code
                        print e
                        ret["errorMsg"] =  ret["errorMsg"] + "repay_loan调用后台过程出错，联系管理员"
                else:
                    pass
                Log().info("pay_loan mifan account confirm id number: %d result error code: %s and error message: %s " %(apply_item.id,  ret["errorCode"], ret["errorMsg"]))
                # 持久化米饭返回结果 message_1 :errorcode , message_2: error message
                extra_apply = ExtraApply(apply = apply_item, message_1 = ret['errorCode'],message_2 = ret['errorMsg'])
                extra_apply.save()
        return HttpResponse("auto_pay done")
    except Exception, e:
        print "excp", e
        traceback.print_exc()
        return HttpResponse("error happen")

def dosomething_out():
    lt = time.localtime()
    d = 60 * (59 - lt[4]) + 60 - lt[5]
    timer = threading.Timer(d, dosomething)
    timer.start()

def dosomething():
    Log().info('开始一次自动代付')
    now = datetime.datetime.now()
    Log().info(now.strftime('%Y-%m-%d %H:%M:%S'))
    auto_pay()
    auto_pay_confirm()
    timer = threading.Timer(60*60, dosomething)
    timer.start()

#dosomething_out()


def get_related_collection_apply_id(apply_id):
    apply = get_object_or_404(Apply, id=apply_id)
    collection_applys = Apply.objects.filter(Q(repayment=apply.repayment) & Q(money=apply.money) & Q(type__in=[Apply.COLLECTION_M0, Apply.COLLECTION_M1, Apply.COLLECTION_M2, Apply.COLLECTION_M3, Apply.COLLECTION_M4]))
    if len(collection_applys) >= 1:
        collection_apply = collection_applys[0]
        return str(collection_apply.id)
    else:
        return 'null'

@csrf_exempt
@page_permission(check_employee)
def add_collection_record(request):
    if request.method == 'POST':
        try:
            emplyee = get_employee(request)
            collection_to = request.POST.get("object")
            will_repay_time = request.POST.get("time")
            content = request.POST.get("content")
            aid = request.POST.get("apply")
            #res = message_client.send_message(phone_no, content.encode("gbk"), 5)
            repay_apply = Apply.objects.get(id=aid)
            record = CollectionRecord(record_type=CollectionRecord.COMMENT, object_type=CollectionRecord.SELF, create_by = emplyee,
                                      collection_note=content, promised_repay_time=None, apply=repay_apply)
            record.save()
            collection_applys = Apply.objects.filter(Q(repayment=repay_apply.repayment) & Q(money=repay_apply.money) & Q(type__in=[Apply.COLLECTION_M0, Apply.COLLECTION_M1, Apply.COLLECTION_M2, Apply.COLLECTION_M3, Apply.COLLECTION_M4]))
            if len(collection_applys) >0:
                record = CollectionRecord(record_type=CollectionRecord.COMMENT, object_type=CollectionRecord.SELF, create_by = emplyee, collection_note=content, promised_repay_time=None, apply=collection_applys[0])
                record.save()
            res=True
            if res:
                Log().info("add collection record success %s" % emplyee.username)
                #return HttpResponse(json.dumps({"result" : u"ok"}))
                return HttpResponse(json.dumps({"error" : u"催记添加成功"}))
            else:
                Log().info("add collection record failed %s" % emplyee.username)
                return HttpResponse(json.dumps({"error" : u"催记添加失败"}))
        except Exception, e:
            print e
            traceback.print_exc()
            Log().info("add collection record failed %s %s" % (emplyee.username, str(e)))
            return HttpResponse(json.dumps({"error" : u"催记添加异常"}))
    return HttpResponse(json.dumps({"error" : u"post only"}))

def get_table1_view(request):
    if request.method == 'GET':
        columns = data_views.get_table1_columns()
        page= render_to_response('operation/table1.html', {"columns" : columns, "datatable" : []},
                                 context_instance=RequestContext(request))
        return page

def get_table2_view(request):
    if request.method == 'GET':
        columns = data_views.get_table2_columns()
        page= render_to_response('operation/table2.html', {"columns" : columns, "datatable" : []},
                                 context_instance=RequestContext(request))
        return page

def get_table3_view(request):
    if request.method == 'GET':
        columns = data_views.get_table3_columns()
        page= render_to_response('operation/table3.html', {"columns" : columns, "datatable" : []},
                                 context_instance=RequestContext(request))
        return page

def get_table4_view(request):
    if request.method == 'GET':
        columns = data_views.get_table4_columns()
        page= render_to_response('operation/table4.html', {"columns" : columns, "datatable" : []},
                                 context_instance=RequestContext(request))
        return page
def get_table3_result_view(request):
    if request.method == 'GET':
        columns = data_views.get_table3_result_columns()
        result_columns = get_table3_result_datatable(request)
        page= render_to_response('operation/table3_result.html', {"result_columns":result_columns,"columns" : columns, "datatable" : []},
                                 context_instance=RequestContext(request))
        return page

@page_permission(check_employee)
def get_repay_modal_batch_view(request):
    if request.method == 'GET':
        token = uuid.uuid1()
        columns = [u"id", u"用户id",u"订单号",u"用户",u"身份证", u"借款金额", u"到账金额", u"借贷方式",u"银行名称", u"申请时间", u"起息日", u"状态"]
        columns = data_views.get_repay_loan_columns()
        page= render_to_response('operation/repay_modal_batch.html', {"token":token,"columns" : columns, "datatable" : []},
                                 context_instance=RequestContext(request))
        return page
@page_permission(check_employee)
def get_pay_loan_view(request):
    if request.method == 'GET':
        columns = data_views.get_pay_loan_columns()
        page= render_to_response('operation/pay_loan.html', {"columns" : columns, "datatable" : []},
                                 context_instance=RequestContext(request))
        return page

@page_permission(check_employee)
def get_repay_loan_view(request):
    if request.method == 'GET':
        columns = data_views.get_repay_loan_columns()
        _qdl = list()
        for strategy in Strategy.objects.all():
            _qd = dict()
            _qd['strategy_id'] = strategy.strategy_id
            _qd['description'] = strategy.description
            _qdl.append(_qd)
            page= render_to_response('operation/repay_loan.html', {"query_strategy": _qdl, "columns" : columns, "datatable" : []},
                                 context_instance=RequestContext(request))
        return page

@page_permission(check_employee)
def get_repay_loan_view4custom(request):
    if request.method == 'GET':
        columns = data_views.get_repay_loan_columns()
        page= render_to_response('operation/repay_loan4custom.html', {"columns" : columns, "datatable" : []},
                                 context_instance=RequestContext(request))
        return page

@page_permission(check_employee)
def get_advance_loan_view(request):
    if request.method == 'GET':
        columns = [] #data_views.get_advanced_loan_columns()
        page= render_to_response('operation/advanced_loan.html', {"columns" : columns, "datatable" : []},
                                 context_instance=RequestContext(request))
        return page

@page_permission(check_employee)
def mifan_account_confirm_idlist(request):
    if request.method == 'GET':

        pay_time = request.GET.get("pay_time")
        pay_amount = request.GET.get("pay_amount", 0)
        if pay_amount:
            pay_amount = int(float(pay_amount) * 100)
        else:
            pay_amount = 0

        token = request.GET.get("token")
        exist_token = redis_client.hget("pay_token",  token)
        if not exist_token:
            ret = redis_client.hsetnx("pay_token", token, 1)
            if ret == 0: #token已经存在
                return HttpResponse(json.dumps({"error" :  "不能重复提交"}))
        else:
            return HttpResponse(json.dumps({"error" : "不能重复提交"}))

        jsondata = {};
        aid_list = json.loads(request.GET[u'id_list'])
        try :
            apply_list  = Apply.objects.filter(Q(id__in = aid_list))
            for apply_item in apply_list:
                    repayment = apply_item.repayment
                    s = Strategy.objects.get(pk = repayment.strategy_id)
                    ret = json.loads(getdata4mifan(send2mifan_confirm(repayment,s)))
                    #mifan 无法判断到账状态，所以米饭已打款就认为打款成功 104
                    if ret['errorCode'] == 104 or ret['errorCode'] == 105:
                        apply_item.status = '2'
                        apply_item.save()
                        try:
                            res = risk_client.pay_loan(repayment.order_number, pay_time, pay_amount)
                            if res.result_code  != 0:
                                ret["errorMsg"] =  ret["errorMsg"] + "没有成功调用后台，联系管理员"
                            bank_card = BankCard.get_pay_card(repayment.user)
                            repay_date = repayment.next_repay_time.strftime("%y-%m-%d")
                            if settings.MIFAN_DEBUG == False:
                                res = message_client.send_message(repayment.user.phone_no, (u"您申请的贷款已经完成打款，卡号:%s，还款日期：%s，借贷信息已提交央行征信。rst客服热线400-606-4728 " % (bank_card_card_number, repay_date)).encode("gbk"), 5)
                                Log().info("send message %s " % res)
                        except Exception, e:
                            traceback.print_exc()
                            #print res.result_code
                            print e
                            ret["errorMsg"] =  ret["errorMsg"] + "repay_loan调用后台过程出错，联系管理员"
                    else:
                        pass
                    jsondata[str(apply_item.id)] = ret["errorMsg"]
                    jsondata[str(apply_item.id) + 'errorCode'] = ret['errorCode']
                    Log().info("pay_loan mifan account confirm id number: %d result error code: %s and error message: %s " %(apply_item.id,  ret["errorCode"], ret["errorMsg"]))
                    # 持久化米饭返回结果 message_1 :errorcode , message_2: error message
                    extra_apply = ExtraApply(apply = apply_item, message_1 = ret['errorCode'],message_2 = ret['errorMsg'])
                    extra_apply.save()
            return HttpResponse(json.dumps(jsondata))
        except Exception, e:
            print "excp", e
            traceback.print_exc()
            jsondata["error"] =  u"mifan account confirm failed"
            return HttpResponse(json.dumps(jsondata))


def get_repay_result(aid,user):

    apply = get_object_or_404(Apply, id = aid)
    repayment = apply.repayment
    installments = InstallmentDetailInfo.objects.filter(repayment=repayment, installment_number=apply.money + 1)
    installment = None
    #if apply.status == '9':
    #    return HttpResponse(json.dumps({"error" : "ok", "msg": "改扣款已经执行成功，不能重复扣款"}))

    if len(installments) == 1:
        installment = installments[0]
    else:
        return u"未找对应的借款信息"

    bank_card = BankCard.get_repay_card(repayment.user)
    if not bank_card:
        return u"未找到还款银行卡"

    #sleep(1)
    Log().info("realtime repay_loan %s " % (aid ))
    #res = bank_client.realtime_pay(repayment.exact_amount, bank_card.get_bank_code(), bank_card_card_number, repayment.user.name, repayment.user.id, 'mifan')
    #TODO: check repay status & amount

    all_repay_money = rest_repay_money = installment.should_repay_amount  - installment.real_repay_amount + installment.repay_overdue  - installment.reduction_amount
    real_repay_money = 0
    repay_money = 0
    res = None
    msg = ""

    if rest_repay_money == 0:
        _update_related_collection_apply(apply)
        return u"扣款已完成"

    while(rest_repay_money > 0):
        if rest_repay_money > 100000:
            repay_money = 100000
        else:
            repay_money = rest_repay_money

        try:
            print repayment.user.name
            print type(repayment.user.name)
            res = bank_client.realtime_pay(repay_money, bank_card.get_bank_code(), bank_card_card_number, repayment.user.name, repayment.user.id, 'mifan')
        except Exception, e:
            Log().error("access bank service occur a exception:  except:  %s" % str(e))
            traceback.print_exc()
            print e
        msg = res.err_msg if  res and res.err_msg else ""
        Log().info(u"repay_for %s %s %s %d %d done " % (bank_card.get_bank_code(), bank_card_card_number, repayment.user.name, repayment.user.id, repay_money ))
        Log().info("do realtime repay res:%s msg:%s" % (res.retcode, msg.decode("utf-8")))

        rest_repay_money -= repay_money
        if res.retcode != 0:
            break
        else:
            real_repay_money += repay_money
    # pay_loan
    #找到对应的催收apply

    try:
        relate_colleciton_apply_id = get_related_collection_apply_id(apply.id)
        staff = Employee.objects.get(user = user)
    except Exception, e:
        traceback.print_exc()
        print e
        Log().info(u"获取催收apply 和 user 失败%s" % str(e))
    if res and res.retcode == 0: #扣款成功
        try:
            apply.status = Apply.REPAY_SUCCESS
            apply.save()
            note = u"扣款成功 卡号:%s 金额:%s" % (bank_card_card_number, real_repay_money)
            record = CollectionRecord(record_type=CollectionRecord.REPAY, object_type=CollectionRecord.SELF, create_by = staff,
                                  collection_note=note, promised_repay_time=None, apply=apply)
            record.save()
            if relate_colleciton_apply_id != "null":
                relate_apply = Apply.objects.get(id = relate_colleciton_apply_id)
                record = CollectionRecord(record_type=CollectionRecord.REPAY, object_type=CollectionRecord.SELF, create_by = staff,
                                      collection_note=note, promised_repay_time=None, apply=relate_apply)
                record.save()
            _update_related_collection_apply(apply)
        except Exception, e:
            traceback.print_exc()
            print e
            Log().info(u"改订单号状态,添加record,跟新催收过程出错")
        try:
            Log().info(u"start update risk_server")
            res = risk_client.repay_loan(repayment.order_number, installment.installment_number)
            if res.result_code  != 0:
                Log().info(u"扣款已经成功, server更新失败，请联系管理员 order_number: %s  installment_number: %d"  % (repayment.order_number, installment.installment_number))
                return u"扣款已经成功, server更新失败，请联系管理员"
            Log().info(u" server更新成功")
        except Exception, e:
            traceback.print_exc()
            #print res.result_code
            print e
            return u"扣款已经成功, 系统更新失败，请联系管理员"
        return u"扣款成功"
    elif real_repay_money > 0: #部分成功
        try:
            installment.real_repay_amount += real_repay_money
            installment.save()
            apply.status = 'd'
            apply.save()
            note = u"扣款部分成功 卡号:%s 扣款金额:%f 成功金额:%f, 最后一笔失败原因%s" % (bank_card_card_number, all_repay_money/100.0, real_repay_money/100.0, msg.decode("utf-8"))
            record = CollectionRecord(record_type=CollectionRecord.REPAY, object_type=CollectionRecord.SELF, create_by = staff,
                                  collection_note=note, promised_repay_time=None, apply=apply)
            record.save()
            if relate_colleciton_apply_id != "null":
                relate_apply = Apply.objects.get(id = relate_colleciton_apply_id)
                record = CollectionRecord(record_type=CollectionRecord.REPAY, object_type=CollectionRecord.SELF, create_by = staff,
                                      collection_note=note, promised_repay_time=None, apply=relate_apply)
                record.save()
            return u"部分成功"
        except Exception, e:
            traceback.print_exc()
            print e
            Log().info(u"改订单号状态,添加record部分扣款成功 过程出错")
    else:
        try:
            apply.status = 'c' #失败
            apply.save()
            note = u"扣款失败 卡号:%s 扣款金额:%f 失败原因:%s" % (bank_card_card_number, all_repay_money/100.0, msg.decode("utf-8"))
            record = CollectionRecord(record_type=CollectionRecord.REPAY, object_type=CollectionRecord.SELF, create_by = staff,
                                  collection_note=note, promised_repay_time=None, apply=apply)
            record.save()
            if relate_colleciton_apply_id != "null":
                relate_apply = Apply.objects.get(id = relate_colleciton_apply_id)
                record = CollectionRecord(record_type=CollectionRecord.REPAY, object_type=CollectionRecord.SELF, create_by = staff,
                                      collection_note=note, promised_repay_time=None, apply=relate_apply)
                record.save()
            return  msg.decode("utf-8")
        except Exception, e:
            traceback.print_exc()
            print e
            Log().info(u"改订单号状态,添加record部分扣款失败 过程出错")

@login_required
@page_permission(check_employee)
def repay_batch_idlist(request):
    if request.method == 'GET':
        #print request.GET[u'id_list']
        jsondata = {};
        aid_list = json.loads(request.GET[u'id_list'])
        staff = Employee.objects.get(user = request.user)
        print staff
        try :
            token = request.GET.get("token")
            exist_token = redis_client.hget("repay_token",  token)
            if not exist_token:
                ret = redis_client.hsetnx("repay_token", token, 1)
                if ret == 0: #token已经存在
                    return HttpResponse(json.dumps({"error" :  "不能重复提交"}))
            else:
                return HttpResponse(json.dumps({"error" : "不能重复提交"}))

            applys = Apply.objects.filter(Q(id__in = aid_list))
            for apply_item in applys:
                #print request.user ,"type user:", type(request.user)
                jsondata[apply_item.id] =  get_realtime_repay_result(apply_item,"installment",'0.0',"realtime_repay",staff)
                #jsondata[apply_item.id] =  get_repay_result(apply_item.id,request.user)
        except Exception, e:
            print "excp", e
            Log().info("do batch repay list confirm fail")
            traceback.print_exc()
            return HttpResponse(json.dumps(jsondata))
        #for item in range(len(ad_list)):
        #   print ad_list[item]
        return HttpResponse(json.dumps(jsondata))

@page_permission(check_employee)
def mifan_confirm_idlist(request):
    if request.method == 'GET':
        #print request.GET[u'id_list']

        token = request.GET.get("token")
        exist_token = redis_client.hget("pay_token",  token)
        if not exist_token:
            ret = redis_client.hsetnx("pay_token", token, 1)
            if ret == 0: #token已经存在
                return HttpResponse(json.dumps({"error" :  "不能重复提交"}))
        else:
            return HttpResponse(json.dumps({"error" : "不能重复提交"}))

        jsondata = {};
        aid_list = json.loads(request.GET[u'id_list'])

        try :
            applys = Apply.objects.filter(Q(id__in = aid_list))
            for apply_item in applys:
                if luhn_check(apply_item.repayment.bank_card.card_number):
                    if apply_item.status == 'y' or apply_item.status == '0':
                        if apply_item.repayment.user.phone_no in mifan_block_list:
                            jsondata[str(apply_item.id)] = u"内部黑名单，无法向米饭请款"
                            jsondata[str(apply_item.id) + 'errorCode'] = "10000"
                            Log().info("pay_loan mifan id number: %d result error code: %s and error message: %s " %(apply_item.id,  "10000",u"内部黑名单，无法向米饭请款"))
                            # 持久化米饭返回结果 message_1 :errorcode , message_2: error message
                            extra_apply = ExtraApply(apply = apply_item, message_1 = "1000",message_2 = u"内部黑名单，无法向米饭请款")
                            extra_apply.save()
                            continue
                        repayment = apply_item.repayment
                        s = Strategy.objects.get(pk = repayment.strategy_id)
                        Log().info("send to  mifan data start on id number: %d"  %(apply_item.id))
                        ret = json.loads(getdata4mifan(send2mifan(repayment,s)))
                        Log().info("send to  mifan data end   on id number: %d"  %(apply_item.id))
                        if ret["errorMsg"] == "success":
                            apply_item.status = '1'
                            apply_item.save()
                        else:
                            apply_item.status = '4'
                            apply_item.save()
                        Log().info("start Persistence result on id number: %d"  %(apply_item.id))
                        jsondata[str(apply_item.id)] = ret["errorMsg"]
                        jsondata[str(apply_item.id) + 'errorCode'] = ret['errorCode']
                        Log().info("pay_loan mifan id number: %d result error code: %s and error message: %s " %(apply_item.id,  ret["errorCode"], ret["errorMsg"]))
                        # 持久化米饭返回结果 message_1 :errorcode , message_2: error message
                        extra_apply = ExtraApply(apply = apply_item, message_1 = ret['errorCode'],message_2 = ret['errorMsg'])
                        extra_apply.save()
                        Log().info("end Persistence result on id number: %d"  %(apply_item.id))
                    else:
                        pass
                else:
                    apply_item.status = '4'
                    apply_item.save()
                    jsondata[str(apply_item.id)] = "银行卡校验出错,提醒用户更新银行卡信息"
                    jsondata[str(apply_item.id) + 'errorCode'] =  "90000"

        except Exception, e:
            print "excp", e
            traceback.print_exc()
            jsondata["error"] =  u"mifan failed"
            return HttpResponse(json.dumps(jsondata))
        #for item in range(len(ad_list)):
        #   print ad_list[item]
        return HttpResponse(json.dumps(jsondata))
    else:
        jsondata = {'name':'jiang'}
        return HttpResponse(json.dumps(jsondata))

def get_mifan_confirm_view(request):
    if request.method == 'GET':
        token = uuid.uuid1()
        columns = [u"申请id", u"用户", "资金渠道", u"借款金额", u"到账金额", u"借贷方式", u"申请时间", u"起息日", u"状态", u"米饭打款状态码"]
        columns = data_views.get_pay_loan_columns()
        page= render_to_response('operation/mifan_confirm.html', {"token" : token ,"columns" : columns,"datatable" : []},
                                 context_instance=RequestContext(request))
        return page

def get_mifan_confirm_account_view(request):
    if request.method == 'GET':
        token = uuid.uuid1()
        columns = [u"申请id", u"用户", "资金渠道", u"借款金额", u"到账金额", u"借贷方式", u"申请时间", u"起息日", u"状态", u"米饭打款状态码"]
        columns = data_views.get_pay_loan_columns()
        page= render_to_response('operation/mifan_confirm_account.html', {"token" : token, "columns" : columns,"datatable" : []},
                                 context_instance=RequestContext(request))
        return page


def get_pay_modal_view(request, apply_id):
    if request.method == 'GET':
        apply = get_object_or_404(Apply, id=apply_id)
        bank_card = BankCard.get_pay_card(apply.repayment.user)
        columns = [] #data_views.get_advanced_loan_columns()
        page= render_to_response('operation/pay_modal.html', {"columns" : columns, "datatable" : [], "payment": apply.repayment, "apply": apply, "bank_card": bank_card},
                                 context_instance=RequestContext(request))
        return page

def get_all_should_repay_periods(apply):
    peroids = []
    #number = apply.money + 1
    #installments = InstallmentDetailInfo.objects.filter( Q(repayment=apply.repayment) & Q( installment_number__gte =  number))
    # installments = InstallmentDetailInfo.objects.filter( Q(repayment=apply.repayment) & Q( installment_number__gte =  (apply.money + 1 )))
    installments = InstallmentDetailInfo.objects.filter( Q(repayment=apply.repayment) & ~Q( repay_status__in = [3, 8]))
    for i in installments:
        if i.repay_status in [3, 8, 9]:
            # pass
            continue
        peroids.append(i.installment_number)
    print "计算all peroids", peroids
    return peroids

def get_should_repay_periods(apply):
    peroids = []
    # lupeng
    # zero_installment = InstallmentDetailInfo.objects.filter(repayment=apply.repayment, installment_number=0, repay_status__in=[1, 2]).first()
    # if zero_installment:
        # peroids.append(zero_installment.installment_number)

    #number = apply.money + 1
    #installments = InstallmentDetailInfo.objects.filter( Q(repayment=apply.repayment) & Q( installment_number__gte =  number))
    # installments = InstallmentDetailInfo.objects.filter( Q(repayment=apply.repayment) & Q( installment_number__gte =  (apply.money + 1 )))
    installments = InstallmentDetailInfo.objects.filter( Q(repayment=apply.repayment) & Q( repay_status__in = [1, 2]))

    for i in installments:
        if i.repay_status in [3, 8, 9]:
            continue
            # peroids.append(i.installment_number)
        elif i.repay_status == 7:
            if i.overdue_days != 0:
                peroids.append(i.installment_number)
            else:
                break
        else:
            peroids.append(i.installment_number)
    return peroids

def get_should_repay_amount(peroids_set, apply, platform="lupeng"):
    installments = InstallmentDetailInfo.objects.filter(Q(repayment=apply.repayment) &  Q(installment_number__in = peroids_set))
    amount = 0
    print 'in get_should_repay_amount'
    print installments
    for i in installments:
        amount += i.should_repay_amount + i.repay_overdue - i.reduction_amount - i.real_repay_amount

    print 'amount %s' % amount
    print ' out get_should_repay_amount'
    return amount

def repay_all_amount(repayment):

    print('in can_repay_amount')
    can_repay_all = False
    installments = InstallmentDetailInfo.objects.filter(repayment=repayment, repay_status__in=[1, 2, 5, 7])
    one_installment = installments.first()
    if not one_installment:
        return 0, 0
    rest_amount = 0
    if  one_installment.repay_status not in ['overdue'] and one_installment.installment_number > 3:
        print('can_repay_amount all')

        # if 1:
        # rest_amount = sum([i.should_repay_amount for i in installments])
        # 用户扣款合计=（借款金额/借款期数）*剩余未还期数+借款金额*3%
        # strategy = Strategy2.get(strategy_id=repayment.strategy_id)
        strategy = Strategy2.objects.get(strategy_id=repayment.strategy_id)
        # rest_amount = int(
            # (repayment.apply_amount / strategy.installment_count) * installments.count()
            # + (repayment.apply_amount * 0.03)
            # )
        rest_amount = int(
            (repayment.apply_amount
            - ((repayment.apply_amount / strategy.installment_count) * installments.count())
            ) * 0.03
        )
        print installments
        print repayment.apply_amount                              
        print repayment.apply_amount / strategy.installment_count
        print installments.count()    
        can_repay_all = True

    return can_repay_all, rest_amount

 
def fill_repay_modal_data(apply):
    temp_installment_more = {}
    installments = InstallmentDetailInfo.objects.filter(Q(repayment=apply.repayment) &  Q(installment_number__in = get_should_repay_periods(apply)))
    # temp_installment_more["now_apply_number"] = apply.money + 1 if installments.first() and installments.first().installment_number > 0 else 0
    temp_installment_more["now_apply_number"] = installments.first().installment_number + installments.count() - 1 if installments.first() and installments.first().installment_number > 0 else ""
    temp_installment_more["rest_repay_money"] = get_should_repay_amount(get_should_repay_periods(apply), apply)
    #dingdang
    temp_installment_more["can_repay_all"] = True
    temp_installment_more["all_rest_repay_money"] = get_should_repay_amount(get_all_should_repay_periods(apply), apply)

    #lupeng
    # temp_installment_more["can_repay_all"], temp_installment_more["all_rest_repay_money"] = repay_all_amount(apply.repayment)

    peroids_str = ''
    for i in get_should_repay_periods(apply):
        peroids_str += " "
        peroids_str += str(i)
    temp_installment_more["peroids"] =  peroids_str
    temp_installment_more["repay_principle"] = 0
    temp_installment_more["repay_interest"] = 0 
    temp_installment_more["repay_overdue_interest"] = 0
    temp_installment_more["repay_penalty"] = 0
    temp_installment_more["repay_overdue"] = 0
    temp_installment_more["reduction_amount"] = 0
    temp_installment_more["real_repay_amount"] = 0
    temp_installment_more["should_repay_amount"] = 0
    temp_installment_more["should_repay_amount_collection"] = 0
    temp_installment_more["actual_should_repay_amount"] = 0
    temp_installment_more["actual_should_repay_amount_collection"] = 0
    temp_installment_more["repay_bank_fee"] = 0
    temp_installment_more["repay_fee"] = 0
    for i in installments:
        temp_installment_more["repay_principle"] += i.repay_principle 
        temp_installment_more["repay_interest"] += i.repay_interest 
        temp_installment_more["repay_overdue_interest"] += i.repay_overdue_interest 
        temp_installment_more["repay_penalty"] += i.repay_penalty
        temp_installment_more["repay_overdue"] += i.repay_overdue
        temp_installment_more["reduction_amount"] += i.reduction_amount
        temp_installment_more["real_repay_amount"] += i.real_repay_amount
        temp_installment_more["should_repay_amount"] += i.should_repay_amount
        temp_installment_more["should_repay_amount_collection"] += i.should_repay_amount - i.repay_fee
        # temp_installment_more["actual_should_repay_amount"] += i.should_repay_amount + i.repay_overdue - i.reduction_amount - i.real_repay_amount
        temp_installment_more["actual_should_repay_amount"] += i.repay_overdue + i.repay_fee
        temp_installment_more["actual_should_repay_amount_collection"] += i.should_repay_amount + i.repay_overdue
        temp_installment_more["repay_bank_fee"] += i.repay_bank_fee
        temp_installment_more["repay_fee"] += i.repay_fee 
    return temp_installment_more


def get_repay_modal_view(request, apply_id):
    if request.method == 'GET':
        apply = get_object_or_404(Apply, id=apply_id)
        repayment = apply.repayment
        strategy = Strategy.objects.get(pk = repayment.strategy_id)
        installments = InstallmentDetailInfo.objects.filter(repayment=repayment, installment_number=apply.money + 1)
        installment = None
        if len(installments) == 1:
            installment = installments[0]
        else:
            return HttpResponse(json.dumps({"error" : "ok", "msg": "未找对应的借款信息"}))
        #installment["rest_repay_amount"] = installment.should_repay_amount  - installment.real_repay_amount + installment.repay_overdue
        #installment["repay_all"] = installment.should_repay_amount + installment.repay_overdue
        #installment["base_amount"] = repayment.apply_amount / strategy.installment_count
        #installment["base_interest"] = installment.should_repay_amount - installment.base_amount

        installment_more = {}
        installment_more = fill_repay_modal_data(apply)
        #rest_repay_money = installment.should_repay_amount  - installment.real_repay_amount + installment.repay_overdue
        #installment_more["rest_repay_amount"] = installment.should_repay_amount  - installment.real_repay_amount + installment.repay_overdue - installment.reduction_amount
        #installment_more["repay_all"] = installment.should_repay_amount + installment.repay_overdue -  installment.reduction_amount
        #installment_more["base_amount"] = repayment.apply_amount / strategy.installment_count
        #installment_more["base_interest"] = installment.should_repay_amount - installment_more["base_amount"]
        #installment_more["now_apply_number"] = installment.installment_number
        ##print installment_more
        bank_card = BankCard.get_repay_card(apply.repayment.user)
        columns = [] #data_views.get_advanced_loan_columns()
        token = uuid.uuid1()
        #collection_apply_id = get_related_collection_apply_id(apply_id)
        page= render_to_response('operation/repay_modal.html', {"apply_id" :apply_id,"installment": installment, "columns" : columns, "datatable" : [], "payment": apply.repayment, "apply": apply, "installment_more": installment_more,
            "bank_card": bank_card,  "token":token, "strategy": Strategy2.objects.get(strategy_id=apply.repayment.strategy_id)},
                                 context_instance=RequestContext(request))
        return page

def get_repay_modal_view4custom(request, apply_id):
    if request.method == 'GET':
        apply = get_object_or_404(Apply, id=apply_id)
        repayment = apply.repayment
        strategy = Strategy.objects.get(pk = repayment.strategy_id)
        installments = InstallmentDetailInfo.objects.filter(repayment=repayment, installment_number=apply.money + 1)
        installment = None
        if len(installments) == 1:
            installment = installments[0]
        else:
            return HttpResponse(json.dumps({"error" : "ok", "msg": "未找对应的借款信息"}))
        rest_repay_money = installment.should_repay_amount  - installment.real_repay_amount + installment.repay_overdue
        #installment["rest_repay_amount"] = installment.should_repay_amount  - installment.real_repay_amount + installment.repay_overdue
        #installment["repay_all"] = installment.should_repay_amount + installment.repay_overdue
        #installment["base_amount"] = repayment.apply_amount / strategy.installment_count
        #installment["base_interest"] = installment.should_repay_amount - installment.base_amount
        installment_more = {}
        installment_more["rest_repay_amount"] = installment.should_repay_amount  - installment.real_repay_amount + installment.repay_overdue - installment.reduction_amount
        installment_more["repay_all"] = installment.should_repay_amount + installment.repay_overdue -  installment.reduction_amount
        installment_more["base_amount"] = repayment.apply_amount / strategy.installment_count
        installment_more["base_interest"] = installment.should_repay_amount - installment_more["base_amount"]
        print installment_more
        bank_card = BankCard.get_repay_card(apply.repayment.user)
        columns = [] #data_views.get_advanced_loan_columns()
        token = uuid.uuid1()
        #collection_apply_id = get_related_collection_apply_id(apply_id)
        page= render_to_response('operation/repay_modal4custom.html', {"apply_id" :apply_id,"installment": installment, "columns" : columns, "datatable" : [], "payment": apply.repayment, "apply": apply, "installment_more": installment_more,
                                 "bank_card": bank_card, "rest_amount": rest_repay_money, "token":token},
                                 context_instance=RequestContext(request))
        return page


def pay_amount_action(aid, type, pay_amount=0, pay_time= None):
    """代扣修改直接返回成功"""
    # order = get_object_or_404(Apply, pk=aid)
    # repayment = order.repayment
    # order.status = Apply.PAY_SUCCESS
    # order.save()
    # risk_client.pay_loan(repayment.order_number, pay_time, pay_amount)
    # return {'code': 0, 'msg': u'打款成功'}

    # 下面为原有代码
    print 'in pay_amount'
    if pay_amount:
        pay_amount = int(float(pay_amount) * 100)
    else:
        pay_amount = 0

    apply = get_object_or_404(Apply, id = aid)
    repayment = apply.repayment
    print repayment.user
    bank_card = BankCard.get_pay_card(repayment.user)
    if not bank_card:
        return {"error" : "ok", "msg": "未找到借款款银行卡"}
    #sleep(1)
    print type
    print '----------'
    bank_card_card_number = bank_card.card_number
    if type == 'realtime_pay':
        print '1111111'
        Log().info("realtime pay_loan %s start" % aid)
        try:
            pass
            # res = message_client.send_message(repayment.user.phone_no, (u"您申请的贷款已经完成打款，卡号:%s，借贷信息已提交央行征信。rst客服400-606-4728" % bank_card_card_number).encode("gbk"), 5)
        except Exception,e:
            Log().error("call message service occur a exception:  except:  %s" % str(e))

        # print '2222222'
        # Log().info("send message %s " % res)
        try:
            #res = bank_client.collect(repayment.exact_amount, bank_card.get_bank_code(), bank_card_card_number, repayment.user.name, repayment.user.id)
            res = Q()
            res.retcode = 0
            res.err_msg = ''
        except Exception as e:
            return {"error" : "ok", "msg": str(e)}

        Log().info(u"pay_for %s %s %s %d %d done" % (bank_card.get_bank_code(), bank_card_card_number, repayment.user.name, repayment.user.id, repayment.exact_amount))
        Log().info("realtime pay_loan %s done" % aid)
        #res = {}
        #res['err_msg'] = u"成功"
        #return HttpResponse(json.dumps({"error" : "failed", "msg": res['err_msg']}))
        msg = res.err_msg if  res.err_msg else u"打款成功"
        print '3333'
        if res.retcode == 0:
            apply.status = Apply.PAY_SUCCESS
            apply.save()
            risk_client.pay_loan(repayment.order_number, pay_time, pay_amount)
        else:
            apply.status = Apply.PAY_FAILED
            apply.save()

        return {"error" : "ok", "msg": msg, 'code': 0}
    elif type == 'comfirm_success':
        print 'ccccccccccccccccccc'
        Log().info("comfirm pay_loan success %s " % aid)
        if apply.status != Apply.PAY_SUCCESS:
            apply.status = Apply.PAY_SUCCESS
            apply.save()
            risk_client.pay_loan(repayment.order_number, pay_time, pay_amount)
            repay_date = repayment.next_repay_time.strftime("%y-%m-%d")
            # res = message_client.send_message(repayment.user.phone_no, (u"您申请的贷款已经完成打款，卡号:%s，还款日期：%s，借贷信息已提交央行征信。rst客服热线400-606-4728 " % (bank_card_card_number, repay_date)).encode("gbk"), 5)
            # Log().info("send message %s " % res)
        else:
            risk_client.pay_loan(repayment.order_number, pay_time, pay_amount)

        return {"error" : "ok", "msg": "", 'code': 0}
    elif type == 'comfirm_failed':
        Log().info("comfirm pay_loan failed %s " % aid)
        apply.status = Apply.PAY_FAILED
        apply.save()
        return {"error" : "ok", "msg": "", 'code': 500}


@csrf_exempt
def do_realtime_pay_action(request):
    if request.method == 'GET':
        print 'dddddddddddddddd'
        aid = request.GET.get('id', None) or request.GET.get("aid", None)
        type = request.GET.get("type")
        pay_time = request.GET.get("pay_time")
        pay_amount = request.GET.get("pay_amount", 0)

        result = pay_amount_action(aid, type, pay_amount, pay_time)

        return HttpResponse(json.dumps(result))



@login_required
@page_permission(check_employee)
def do_realtime_pay_action_batch(request):
    if request.method == 'GET':
        #print request.GET[u'id_list']
        jsondata = {};
        aid_list = request.GET[u'id_list'][1:-1].split(',')
        print 'aid_list', aid_list
        staff = Employee.objects.get(user = request.user)
        type = request.GET.get("type")
        pay_time = request.GET.get("pay_time")

        print staff
        try :
            token = request.GET.get("token")
            exist_token = redis_client.hget("repay_token",  token)
            if not exist_token:
                ret = redis_client.hsetnx("repay_token", token, 1)
                if ret == 0: #token已经存在
                    return HttpResponse(json.dumps({"error" :  "不能重复提交"}))
            else:
                return HttpResponse(json.dumps({"error" : "不能重复提交"}))

            applys = Apply.objects.filter(Q(id__in = aid_list))
            for apply_item in applys:
                msgs = pay_amount_action(apply_item.id, type, pay_time=pay_time)
                print msgs
                if msgs:
                    msg = msgs.get('msg') or 'success'
                else:
                    msg = '错误'

                jsondata[apply_item.id] = msg
                print jsondata
                #jsondata[apply_item.id] =  get_repay_result(apply_item.id,request.user)
        except Exception, e:
            print "excp", e
            Log().info("do batch repay list confirm fail")
            traceback.print_exc()
            return HttpResponse(json.dumps(jsondata))
        #for item in range(len(ad_list)):
        #   print ad_list[item]
        return HttpResponse(json.dumps({'code': 0, 'msg': u'批量打款成功', 'data': jsondata}))




def _update_related_collection_apply(apply, status=None):
    print 'in _update_related_collection_apply'
    collection_apply = get_relative_apply(apply)
    if collection_apply != None:
        if not status:
            if collection_apply.type == Apply.COLLECTION_M0:
                collection_apply.status = Apply.REPAY_SUCCESS
            else:
                collection_apply.status = Apply.COLLECTION_SUCCESS
        else:
            collection_apply.status = status
        collection_apply.save()
    print 'out _update_related_collection_apply'


def try_to_get_should_repay_amount(apply,repay_type,try_to_amount,channel):
    try:
        print 'type apply',type(apply)
        ''' 浮点数有可能会差一分钱'''
        # try_to_amount= int(round(float(try_to_amount) * 100,2) )
        try_to_amount= int(try_to_amount)
        if try_to_amount < 0:
            raise Exception("金额不能小于零")
        print "try_to_amount", try_to_amount
        if channel == "realtime_repay":
            if repay_type == 'installment':
                return get_should_repay_amount(get_should_repay_periods(apply), apply)
            # elif repay_type == 'repayment':
                # repayment = apply.repayment
                # installments = InstallmentDetailInfo.objects.filter(repayment=repayment, repay_status__in=[1, 2, 5, 7])
                # strategy = Strategy2.objects.get(strategy_id=repayment.strategy_id)

                # rest_amount = int(
                    # (repayment.apply_amount
                    # - ((repayment.apply_amount / strategy.installment_count) * installments.count())
                    # ) * 0.03
                # )
                # return rest_amount
                # return get_should_repay_amount(get_all_should_repay_periods(apply), apply)
            else:
                return try_to_amount
        else:
            return try_to_amount
    except Exception, e:
        traceback.print_exc()
        print e
        Log().info(u"error:%s" % str(e))
        raise Exception("计算银行扣款金额异常" + str(e))

def try_to_get_repay_bank_amount(apply,try_to_repay_amount):
    # return 2, 'ok', try_to_repay_amount

    repay_code = 0
    try:
        ret_msg = ""
        #print "try_to_amount",try_to_repay_amount 
        #print apply.repayment.user.name
        print "apply", apply
        print "apply.repayment", apply.repayment
        print try_to_repay_amount
        # bank_card = BankCard.objects.get(owner=apply.repayment.user)
        bank_card = apply.repayment.bank_card
        repayment = apply.repayment
        user = repayment.user
        if bank_card == None:
            raise Exception("获取银行卡错误")
        print 'ddddddddddddddddd'
        rest_repay_money = int(try_to_repay_amount)
        actual_amount = 0
        res = None
        if rest_repay_money < 0:
            raise Exception("金额不能小于零")

        while(rest_repay_money > 0):
            if rest_repay_money > 1000000:
                repay_money = 1000000
            else:
                repay_money = rest_repay_money
            # print client.collect(10000, 1, '6217852000003225128', '刘小军', '13928449141', 1, 'test', '测试', 1, '', '', 0, '421182198701160214', 'test')

            # bank_state_number = BankStatement.objects.filter(bankcard_id=bank_card).order_by("-id").first()
            # bank_order_number = bank_state_number.pre_order_number if bank_state_number else ""
            bank_order_number = 0


            print "order_number: %s, repay_money: %s, user_id: %s, card_number: %s, user_name: %s, phone_no: %s, bank_name: %s, id_no: %s" % (
                bank_order_number, repay_money, user.id, repayment.bank_card.card_number, user.name, user.phone_no, bank_card.bank_name, user.id_no)

            # res = bank_client.collect(repay_money, user.id, repayment.bank_card.card_number, user.name, user.phone_no, bank_card.bank_name, 'kuaifutong', '测试', 1, '', '', 0, user.id_no, 'lupeng', bank_order_number)
            # res = bank_client.collect(
                # repay_money, user.id, repayment.bank_card.card_number, user.name.encode('utf8'), user.phone_no,
                # # bank_card.bank_name.encode('utf8'), 'kuaifutong', '测试', 1, '', '', 0, user.id_no, 'lupeng', bank_order_number)
                # '中国银行', 'kuaifutong', '测试', 1, '', '', 0, user.id_no, 'lupeng', bank_order_number)
            res = Q()
            setattr(res, 'retcode', 0)

            print '--* --' * 30
            print res
            print '  -* --' * 30
            msg = res.err_msg if  res and res.err_msg else ""
            Log().info(u"repay_for %s %s %s %d %d done " % (bank_card.get_bank_code(), bank_card.card_number, apply.repayment.user.name, apply.repayment.user.id, repay_money ))
            # Log().info("do realtime repay res:%s msg:%s" % (res.retcode, msg.decode("utf-8")))

            # bank_state = BankStatement.objects.filter(apply=apply, pre_order_number=bank_order_number, status=1).first()
            if res.retcode not in [0, 1]:
                #raise Exception("银行扣款过程错误码" + res.retcode + ", 错误信息" + msg)
                ret_msg = "银行扣款过程错误码" + str(res.retcode) + ", 错误信息" + str(msg)
                break

            rest_repay_money -= repay_money
            actual_amount += repay_money


        if res.retcode < 0:
            if rest_repay_money == int(try_to_repay_amount):
                repay_code = 3
            else:
                repay_code = 1

        return res.retcode, ret_msg, actual_amount, repay_code
    except Exception, e:
        traceback.print_exc()
        print str(e)
        Log().info("error: %s" % str(e))
        raise Exception("银行扣款过程异常:" + str(e))

def get_relative_apply(apply):
    if apply.type == Apply.REPAY_LOAN:
        print "here1"
        relate_apply =  Apply.objects.filter(Q(repayment=apply.repayment) & Q(money=apply.money) & Q(type__in=[Apply.COLLECTION_M0, Apply.COLLECTION_M1, Apply.COLLECTION_M2, Apply.COLLECTION_M3, Apply.COLLECTION_M4]))
        if len(relate_apply) != 1:
            return None
    else:
        relate_apply = Apply.objects.filter(repayment=apply.repayment, money=apply.money, type=Apply.REPAY_LOAN)
        if len(relate_apply) != 1:
            #raise Exception('apply 错误')
            return None
    print 'relate_apply', relate_apply[0].id
    return relate_apply[0]      

def add_record(apply,actual_amount,staff,try_to_amount,bank_ret_msg):
    try:
        ''' 运营扣款'''
        bank_card = BankCard.get_repay_card(apply.repayment.user)
        
        relate_apply = get_relative_apply(apply)
        
        note = u"试图扣款%0.2f 扣款成功 卡号:%s 金额:%0.2f ,%s" % (try_to_amount/100.0,bank_card.card_number, actual_amount/100.0 ,bank_ret_msg)
        extra_data = collection_extra_data(apply)
        record = CollectionRecord(record_type=CollectionRecord.REPAY, object_type=CollectionRecord.SELF, create_by = staff,
                              collection_note=note, promised_repay_time=None, apply=apply, **extra_data)
        record.save()
        # if relate_apply != None: 
            #  print "relate_apply.id", relate_apply.id
            #  record = CollectionRecord(record_type=CollectionRecord.REPAY, object_type=CollectionRecord.SELF, create_by = staff,
            #                       collection_note=note, promised_repay_time=None, apply=relate_apply)
            # record.save()
    except Exception, e:
        traceback.print_exc()
        print e
        Log().info(u"error:%s" % str(e))
        raise Exception("添加扣款记录过程异常")

def add_record4audit(check_apply, apply,actual_amount,staff):
    try:
        ''' 运营扣款'''
        relate_apply = get_relative_apply(apply)
        note = u"财务复核确认到账金额:%0.2f" % ( actual_amount/100.0)
        extra_data = collection_extra_data(apply)
        record = CollectionRecord(record_type=CollectionRecord.REPAY, object_type=CollectionRecord.SELF, create_by = staff,
                              collection_note=note, promised_repay_time=None, apply=apply, check_apply=check_apply, **extra_data)
        record.save()
        if relate_apply != None: 
            record = CollectionRecord(record_type=CollectionRecord.REPAY, object_type=CollectionRecord.SELF, create_by = staff,
                                  collection_note=note, promised_repay_time=None, apply=relate_apply, check_apply=check_apply)
            record.save()
    except Exception, e:
        traceback.print_exc()
        print e
        Log().info(u"error:%s" % str(e))
        raise Exception("添加扣款记录过程异常")

def get_repay_status(repay_type):
    """还款英文, 对应的 code"""

    repay_status_dic = {
        'installment': 1,
        'repayment': 2,
        'custome': 3,
        # 'auto': 4
    }

    repay_status = repay_status_dic.get(repay_type, repay_type or 4)

    return repay_status


def get_repay_status_name(repay_status, repay_code):
    """还款 code, 对应的中文"""

    repay_status_dic = {
        # 40: u'自动扣款成功',
        # 41: u'自动扣款部分成功',
        # # 42: u'自动扣款异常',
        # 43: u'自动扣款失败',

        10: u'扣款成功',
        11: u'扣款部分成功',
        # 12: u'扣款异常',
        13: u'扣款失败',

        20: u'结清成功',
        21: u'结清部分成功',
        # 22: u'结清异常',
        23: u'结清失败',

        30: u'自定义扣款成功',
        31: u'自定义扣款部分成功',
        # 32: u'自定义扣款异常',
        33: u'自定义扣款失败',
    }

    repay_status_code = int(str(repay_status) + str(repay_code))

    return repay_status_dic.get(repay_status_code, str(repay_status_code))


def get_payee_name(apply, staff):
    apply_type = apply.type
    payee_name = u'auto'
    if apply_type in ['a', 'b', 'd', 'e', 'g', 'h']:
        collection_review = CollectionRecord.objects.filter(apply=apply, record_type=CollectionRecord.DISPATCH).order_by("-id").first()
        print apply
        print CollectionRecord.DISPATCH
        print collection_review
        if collection_review:
            payee_name = collection_review.create_by.user.username

    elif apply_type in ['p']:
        print 'staff:'
        print staff
        if staff:
            payee_name = staff.user.username

    return payee_name

def refresh_risk_server(actual_amount,apply,repay_channel, bank_repay_code, try_to_repay_amount, staff=None, repay_status=0):
    print 'in refresh_risk_server'
    REPAY_CHANNEL_TYPE = {
        'realtime_repay' : 1,
        'alipay_repay' : 3,
        'topublic_repay' : 4,
    }
    print locals()
    try:
        Log().info(u"start update risk_server")
        # bank_card = BankCard.get_repay_card(apply.repayment.user)
        bank_card = apply.repayment.bank_card
        try:

            payee_name = get_payee_name(apply, staff)
            repay_status_name = get_repay_status_name(repay_status, bank_repay_code)
            # repay_status_name = '123'
            print apply.repayment.order_number
            print actual_amount
            print REPAY_CHANNEL_TYPE[repay_channel]
            payee_name = payee_name.encode('utf8')
            repay_status_name = repay_status_name.encode('utf8')
            print payee_name
            print repay_status_name
            res = risk_client.repay_loan(apply.repayment.order_number, actual_amount, REPAY_CHANNEL_TYPE[repay_channel], bank_card.id, payee_name, repay_status_name)
            print 'refresh ' * 30
            print res
        except Exception, e:
            traceback.print_exc()
            print e
            raise Exception('无法连接risk')
        #TODO  把要跟新的client 代码打印出来 要重复执行
        if res == None:
           print 'risk error'
        if res.result_code  == 0:
            pass
            #Log().info(u"扣款已经成功, server更新失败，请联系管理员 order_number: %s  "  % (apply.repayment.order_number ))
        else:
            Log().info(u"扣款已经成功, server更新失败，请联系管理员 order_number: %s  "  % (apply.repayment.order_number ))
            raise Exception(u'跟新结果不成功')
        Log().info(u" server更新成功")
    except Exception, e:
        traceback.print_exc()
        print e
        Log().info(u"error:%s" % str(e))
        raise Exception(u"更新后台过程异常")

def get_should_repay_but_real_amount(apply):
    print 'in get_should_repay_but_real_amount'
    installments = InstallmentDetailInfo.objects.filter(Q(repayment=apply.repayment) &  Q(installment_number__in = get_should_repay_periods(apply)))
    print 'sdfa   ' * 200
    print installments
    real_repay_amount = 0
    for i in installments:
        real_repay_amount += i.real_repay_amount
    print "real_repay_amount", real_repay_amount
    print 'out get_should_repay_but_real_amount'
    return real_repay_amount

def update_apply2error_status(apply):
    relate_apply = get_relative_apply(apply)
    apply.status = Apply.REPAY_ERROR
    apply.save()
    if relate_apply != None:
        relate_apply.status = Apply.REPAY_ERROR
        relate_apply.save()

def update_apply_status(apply,actual_amount):
    try: 
        print "actual_amount", actual_amount
        relate_apply = get_relative_apply(apply)
        print "get_should_repay_amount(get_should_repay_periods(apply)",get_should_repay_amount(get_should_repay_periods(apply),apply)
        if get_should_repay_amount(get_should_repay_periods(apply), apply) > 0:
            if get_should_repay_but_real_amount(apply) > 0:
                print "get_should_repay_but_real_amount(apply):", get_should_repay_but_real_amount(apply)
                apply.status = Apply.PARTIAL_SUCCESS
                apply.save()
                if relate_apply != None:
                    relate_apply.status = Apply.PARTIAL_SUCCESS
                    relate_apply.save()
            else:
                if apply.status == Apply.WAIT:
                    apply.status = Apply.REPAY_FAILED
                    apply.save()
                    if relate_apply != None:
                        relate_apply.status = Apply.REPAY_FAILED
                        relate_apply.save()
        else:
            if apply.type == Apply.REPAY_LOAN:
                apply.status = Apply.REPAY_SUCCESS
                apply.save()
                if relate_apply != None:
                    if relate_apply.type == Apply.COLLECTION_M0:
                        relate_apply.status = Apply.REPAY_SUCCESS
                    else:
                        relate_apply.status = Apply.COLLECTION_SUCCESS
                    relate_apply.save()
            else:
                if relate_apply != None:
                    relate_apply.status = Apply.REPAY_SUCCESS
                    relate_apply.save()
                if apply.type == Apply.COLLECTION_M0:
                    apply.status = Apply.REPAY_SUCCESS
                else:
                    apply.status = Apply.COLLECTION_SUCCESS
                apply.save()
    except Exception, e:
        traceback.print_exc()
        print e
        Log().info(u"error:%s" % str(e))
        raise Exception("更新apply过程异常")


''' 银联扣钱过程'''
def get_realtime_repay_result(apply,repay_type,try_to_amount,repay_channel,staff, repay_status=0):
    ''' 算准备扣多少钱

    '''
    print "in get_realtime_repay_result"
    try:
        try_to_repay_amount = try_to_get_should_repay_amount(apply,repay_type,try_to_amount,repay_channel)
        # try_to_repay_amount = 86730
        print 'repay_amount -> ', try_to_repay_amount
        bank_retcode, bank_ret_msg, actual_amount, repay_code =  try_to_get_repay_bank_amount(apply,try_to_repay_amount)
        # if bank_ret_msg == 1:
            # msg = "预扣款中: 请提交用户资料到扣款平台进行审核"
            # apply.status = Apply.WAIT
            # apply.save()
            # add_record(apply, actual_amount,staff,try_to_repay_amount, "bank_statement id :%s. %s" % (bank_state_id, msg))
            # return msg

        print '111' * 100
        print try_to_repay_amount
        print bank_ret_msg + ' 22'
        print actual_amount
        print bank_retcode
        print repay_code

        # actual_amount = actual_amount / 100
        add_record(apply,actual_amount,staff,try_to_repay_amount,bank_ret_msg)
        if actual_amount > 0:
            repay_status = get_repay_status(repay_type)
            refresh_risk_server(actual_amount,apply,repay_channel, repay_code, try_to_repay_amount, staff, repay_status)
            update_apply_status(apply,actual_amount)
        elif actual_amount == 0:
            if apply.status == Apply.PROCESSING or apply.status == Apply.WAIT:
                ''' 添加首次扣款失败短信内容'''
                try:
                    res = message_client.send_message(apply.repayment.user.phone_no, (u"本次账单日还款未成功，请确认在签约还款卡中存入本期应还金额,如有疑问请联系客服。").encode("gbk"), 5)
                except Exception, e:
                    traceback.print_exc()
                    #print res.result_code
                    print e
                apply.status = Apply.REPAY_FAILED
                apply.save()
                relate_apply = get_relative_apply(apply)
                if relate_apply != None:
                    relate_apply.status = Apply.REPAY_FAILED
                    relate_apply.save()
        else:
            pass
        if bank_retcode not in [0, 1]:

            return bank_ret_msg

        return "扣款过程正常" + bank_ret_msg
    except Exception, e:
        traceback.print_exc()
        # print e
        # Log().info("error:%s" % str(e))
        update_apply2error_status(apply)
        return str(e)
    ''' 开始从银行扣钱, 并最终扣得多少钱'''
    ''' 添加扣款记录'''
    ''' 用扣钱的数额 去更新后面的risk server'''
    ''' 改变apply 状态 前面出错 后面状态为出错 不准继续扣款'''

def get_realtime_repay_result_not_bank_way(check_apply,apply,repay_type,try_to_amount,repay_channel,staff, repay_status=0):
    ''' 算准备扣多少钱'''
    try:
        #try_to_repay_amount = try_to_get_should_repay_amount(apply,repay_type,try_to_amount,repay_channel)
        #actual_amount =  try_to_get_repay_bank_amount(apply,try_to_repay_amount)
        
        # try_to_amount= int( round(float(try_to_amount) * 100 ,2))
        try_to_amount= int( round(float(try_to_amount) * 1 ,2))
        add_record4audit(check_apply, apply,try_to_amount,staff)
        #add_record(apply,try_to_amount,staff,try_to_amount)
        repay_status = get_repay_status(repay_type)
        refresh_risk_server(try_to_amount,apply,repay_channel, 0, try_to_amount, staff, repay_status)
        update_apply_status(apply,try_to_amount)
        return "扣款过程正常"
    except Exception, e:
        traceback.print_exc()
        print e
        Log().info(u"error:%s" % str(e))
        update_apply2error_status(apply)
        return str(e)
    ''' 开始从银行扣钱, 并最终扣得多少钱'''
    ''' 添加扣款记录'''
    ''' 用扣钱的数额 去更新后面的risk server'''
    ''' 改变apply 状态 前面出错 后面状态为出错 不准继续扣款'''
    
    
@csrf_exempt
# @page_permission(check_employee)
def new_do_realtime_repay_action(request):
    print "enter new fun"
    if not settings.ALLOW_DEDUCTIONS:
        return JsonResponse({
            "code": -1,
            "msg": u"扣款功能暂停使用"
        })
    aid = request.GET.get("apply_id")
    channel = request.GET.get("channel")
    repay_type = request.GET.get("type")
    # token = request.GET.get("token")
    # exist_token = redis_client.hget("repay_token",  token)
    # if not exist_token:
    #     ret = redis_client.hsetnx("repay_token", token, 1)
    #     if ret == 0: #token已经存在
    #         Log().info("realtime repay_loan %s duplicate token %s" % (aid, token))
    #         return HttpResponse(json.dumps({"error" : "pass", "msg": "不能重复提交"}))
    # else:
    #     Log().info("realtime repay_loan %s duplicate token %s" % (aid, token))
    #     return HttpResponse(json.dumps({"error" : "pass", "msg": "不能重复提交"}))

    print '1111111'
    print aid
    apply = get_object_or_404(Apply, id = aid)
    if apply.status in ['8', '9', 's4']:
        return JsonResponse({
            'code': -1,
            'msg': u'订单已完成催收'
        })
    is_operation = request.GET.get('is_operation', None)
    if 'operation' == is_operation:
        pass
    else:
        if apply.employee != Employee.objects.get(user_id=request.user.id):
            return JsonResponse({
                "code": -1,
                "msg": u'请登录订单对应催收员账号进行扣款'
            })
        # return JsonResponse({'code': -1, 'msg': u'请确认你是否有权限进行扣款操作'})
    _amount = request.GET.get("check_amount")
    try_to_amount = request.GET.get("amount") or _amount
    staff = Employee.objects.get(user = request.user)
    # staff = Employee.objects.get(pk=59)
    if channel == 'realtime_repay':
        # print '3',type(apply)
        msg = get_realtime_repay_result(apply,repay_type,try_to_amount,channel,staff)
        order = Apply.objects.filter(pk=aid).first()
        if order:
            try:
                report_collection(order)
            except:
                print 'report failed: ', order
        if order.status == Apply.REPAY_SUCCESS:
            _msg = '扣款成功'
            order.real_repay_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            order.save()
        elif order.status in [Apply.REPAY_ERROR, Apply.REPAY_FAILED]:
            _msg = u'扣款失败'
        else:
            _msg = msg
        return HttpResponse(json.dumps({"code" : 0, "msg": _msg}))
    elif channel == "alipay_repay" or channel == "topublic_repay":
        try:
            url = request.GET.get("url")
            if not url:
                # redis_client.hdel("repay_token",  token)
                return HttpResponse(json.dumps({"error" : "failed", "msg": "请上传图片"}))
            notes = request.GET.get("notes")
            check_amount = 0
            try:
                check_amount = request.GET.get("check_amount")
                check_amount = int(check_amount)
                # check_amount = int(round(float(check_amount) * 100,2) )
            except Exception, e:
                traceback.print_exc()
                Log().info(u"illegal amount : %s" % check_amount)
                # redis_client.hdel("repay_token",  token)
                return HttpResponse(json.dumps({"error" : "failed", "msg": "请填写正确的凭证金额"}))

            staff = Employee.objects.get(user = request.user)
            Log().info("%s submit %s, url:%s, check_amount:%d" % (staff.username, channel, url, check_amount))
            #print check_amount, notes, url
            check_type = CheckApply.CHECK_ALIPAY if channel == "alipay_repay" else CheckApply.CHECK_TOPUBLIC
            check_apply = CheckApply(create_by=staff, money=check_amount, repayment=apply.repayment, 
                                     status=CheckApply.WAIT, pic=url, type=check_type, notes=notes, 
                                     repay_apply=apply, create_at = datetime.now(), platform = apply.platform,
                                    product = apply.product)
            check_apply.save()
            apply.status = Apply.WAIT_CHECK
            apply.save()

            try:
                report_collection(apply)
                record = CollectionRecord(record_type=CollectionRecord.CHECK_NOTES, object_type=CollectionRecord.SELF, create_by = staff, collection_note=u'本人--' + notes, promised_repay_time=None, apply=apply)
                record.save()
            except:
                pass
            _update_related_collection_apply(apply, Apply.WAIT_CHECK)
            return HttpResponse(json.dumps({"code" : 0, "msg": u"扣款成功进入复核状态"}))
        except Exception, e:
            traceback.print_exc()
            print e
            Log().info(u"new audit apply failed %s" % str(e))
            return HttpResponse(json.dumps({'code': -1, "msg": str(e)}))
    return HttpResponse(json.dumps({'code': -1, "msg":"get only"}))
@login_required
@csrf_exempt
def do_realtime_repay_action(request):
    if request.method == 'GET':
        aid = request.GET.get("aid")
        channel = request.GET.get("channel")
        type = request.GET.get("type")
        token = request.GET.get("token")

        exist_token = redis_client.hget("repay_token",  token)
        if not exist_token:
            ret = redis_client.hsetnx("repay_token", token, 1)
            if ret == 0: #token已经存在
                Log().info("realtime repay_loan %s duplicate token %s" % (aid, token))
                return HttpResponse(json.dumps({"error" : "pass", "msg": "不能重复提交"}))
        else:
            Log().info("realtime repay_loan %s duplicate token %s" % (aid, token))
            return HttpResponse(json.dumps({"error" : "pass", "msg": "不能重复提交"}))

        apply = get_object_or_404(Apply, id = aid)
        repayment = apply.repayment
        installments = InstallmentDetailInfo.objects.filter(repayment=repayment, installment_number=apply.money + 1)
        installment = None
        #if apply.status == '9':
        #    return HttpResponse(json.dumps({"error" : "ok", "msg": "改扣款已经执行成功，不能重复扣款"}))

        if len(installments) == 1:
            installment = installments[0]
        else:
            return HttpResponse(json.dumps({"error" : "ok", "msg": "未找对应的借款信息"}))

        bank_card = BankCard.get_repay_card(repayment.user)
        if not bank_card:
            return HttpResponse(json.dumps({"error" : "ok", "msg": "未找到还款银行卡"}))

        #sleep(1)
        if channel == 'realtime_repay':
            Log().info("realtime repay_loan %s start %s" % (aid, token))
            #res = bank_client.realtime_pay(repayment.exact_amount, bank_card.get_bank_code(), bank_card_card_number, repayment.user.name, repayment.user.id, 'mifan')
            #TODO: check repay status & amount
            amount = installment.should_repay_amount  - installment.real_repay_amount + installment.repay_overdue
            all_repay_money = rest_repay_money = amount
            real_repay_money = 0
            repay_money = 0
            res = None
            msg = ""

            if rest_repay_money == 0:
                _update_related_collection_apply(apply)
                return HttpResponse(json.dumps({"error" : "ok", "msg": "扣款已完成,请勿重复扣款"}))
            while(rest_repay_money > 0):
                if rest_repay_money > 1000000:
                    repay_money = 1000000
                else:
                    repay_money = rest_repay_money

                res = bank_client.realtime_pay(repay_money, bank_card.get_bank_code(), bank_card.card_number, repayment.user.name, repayment.user.id, 'mifan')
                msg = res.err_msg if  res and res.err_msg else ""
                Log().info(u"repay_for %s %s %s %d %d done %s" % (bank_card.get_bank_code(), bank_card.card_number, repayment.user.name, repayment.user.id, repay_money, token))
                Log().info("do realtime repay res:%s msg:%s" % (res.retcode, msg.decode("utf-8")))

                rest_repay_money -= repay_money
                #添加运营扣款record
                record_content = ""
                if res.retcode != 0:
                    break
                else:
                    real_repay_money += repay_money
            # pay_loan
            #找到对应的催收apply
            try:
                relate_colleciton_apply_id = get_related_collection_apply_id(apply.id)
                user = request.user
                staff = Employee.objects.get(user = user)
            except Exception, e:
                traceback.print_exc()
                print e
                Log().info(u"获取催收apply 和 user 失败%s" % str(e))

            if res and res.retcode == 0: #扣款成功
                try:
                    apply.status = Apply.REPAY_SUCCESS
                    apply.save()
                    note = u"扣款成功 卡号:%s 金额:%s" % (bank_card.card_number, real_repay_money)
                    record = CollectionRecord(record_type=CollectionRecord.REPAY, object_type=CollectionRecord.SELF, create_by = staff,
                                          collection_note=note, promised_repay_time=None, apply=apply)
                    record.save()
                    if relate_colleciton_apply_id != "null":
                        relate_apply = Apply.objects.get(id = relate_colleciton_apply_id)
                        record = CollectionRecord(record_type=CollectionRecord.REPAY, object_type=CollectionRecord.SELF, create_by = staff,
                                              collection_note=note, promised_repay_time=None, apply=relate_apply)
                        record.save()
                    _update_related_collection_apply(apply)
                except Exception, e:
                    traceback.print_exc()
                    print e
                    Log().info(u"改订单号状态,添加record,跟新催收过程出错")
                try:
                    Log().info(u"start update risk_server")
                    res = risk_client.repay_loan(repayment.order_number, installment.installment_number)
                    print 'real ' * 30
                    print res
                    if res.result_code  != 0:
                        Log().info(u"扣款已经成功, server更新失败，请联系管理员 order_number: %s  installment_number: %d"  % (repayment.order_number, installment.installment_number))
                    Log().info(u" server更新成功")
                    #if res != 0:
                    #    return HttpResponse(json.dumps({"error" : "ok", "msg": "扣款已经成功, server更新失败，请联系管理员"}))
                except Exception, e:
                    traceback.print_exc()
                    print e
                    return HttpResponse(json.dumps({"error" : "ok", "msg": "扣款已经成功, 系统更新失败，请联系管理员"}))
                return HttpResponse(json.dumps({"error" : "ok", "msg": "扣款成功"}))
            elif real_repay_money > 0: #部分成功
                try:
                    note = u"扣款部分成功 卡号:%s 扣款金额:%f 成功金额:%f, 最后一笔失败原因%s" % (bank_card.card_number, all_repay_money/100.0, real_repay_money/100.0, msg.decode("utf-8"))
                    record = CollectionRecord(record_type=CollectionRecord.REPAY, object_type=CollectionRecord.SELF, create_by = staff,
                                              collection_note=note, promised_repay_time=None, apply=apply)
                    record.save()
                    if relate_colleciton_apply_id != "null":
                        relate_apply = Apply.objects.get(id = relate_colleciton_apply_id)
                        record = CollectionRecord(record_type=CollectionRecord.REPAY, object_type=CollectionRecord.SELF, create_by = staff,
                                              collection_note=note, promised_repay_time=None, apply=relate_apply)
                        record.save()
                    installment.real_repay_amount += real_repay_money
                    installment.save()
                    apply.status = 'd'
                    apply.save()
                    return HttpResponse(json.dumps({"error" : "ok", "msg": "部分成功"}))
                except Exception, e:
                    traceback.print_exc()
                    print e
                    Log().info(u"改订单号状态,添加record部分成功过程出错")
            else:
                try:
                    apply.status = 'c' #失败
                    apply.save()
                    note = u"扣款失败 卡号:%s 扣款金额:%f 失败原因:%s" % (bank_card.card_number, all_repay_money/100.0, msg.decode("utf-8"))
                    record = CollectionRecord(record_type=CollectionRecord.REPAY, object_type=CollectionRecord.SELF, create_by = staff,
                                              collection_note=note, promised_repay_time=None, apply=apply)
                    record.save()
                    if relate_colleciton_apply_id != "null":
                        relate_apply = Apply.objects.get(Q(id = relate_colleciton_apply_id))
                        record = CollectionRecord(record_type=CollectionRecord.REPAY, object_type=CollectionRecord.SELF, create_by = staff,
                                              collection_note=note, promised_repay_time=None, apply=relate_apply)
                        record.save()
                    return HttpResponse(json.dumps({"error" : "failed", "msg": msg.decode("utf-8")}))
                except Exception, e:
                    traceback.print_exc()
                    print e
                    Log().info(u"改订单号状态,添加record失败过程出错")
        elif channel == "alipay_repay" or channel == "topublic_repay":
            try:
                url = request.GET.get("url")
                if not url:
                    redis_client.hdel("repay_token",  token)
                    return HttpResponse(json.dumps({"error" : "failed", "msg": "请上传图片"}))
                notes = request.GET.get("notes")
                check_amount = 0
                try:
                    check_amount = request.GET.get("check_amount")
                    check_amount = int(round(float(check_amount) * 100))
                except Exception, e:
                    traceback.print_exc()
                    Log().info(u"illegal amount : %s" % check_amount)
                    redis_client.hdel("repay_token",  token)
                    return HttpResponse(json.dumps({"error" : "failed", "msg": "请填写正确的凭证金额"}))

                staff = Employee.objects.get(user = request.user)
                Log().info("%s submit %s, url:%s, check_amount:%d" % (staff.username, channel, url, check_amount))
                #print check_amount, notes, url
                check_type = CheckApply.CHECK_ALIPAY if channel == "alipay_repay" else CheckApply.CHECK_TOPUBLIC
                check_apply = CheckApply(create_by=staff, money=check_amount, repayment=apply.repayment, status=CheckApply.WAIT, pic=url, type=check_type, notes=notes, repay_apply=apply, create_at = datetime.now())
                check_apply.save()
                note = u"提交凭证 金额:%d, 类型：%s" % (request.GET.get("check_amount"), check_apply.get_check_type_display())
                record = CollectionRecord(record_type=CollectionRecord.REPAY, object_type=CollectionRecord.SELF, create_by = staff,
                                      collection_note=note, promised_repay_time=None, apply=apply)
                record.save()
                apply.status = Apply.WAIT_CHECK
                apply.save()
                _update_related_collection_apply(apply, Apply.WAIT_CHECK)

                return HttpResponse(json.dumps({"error" : "ok", "msg": "success"}))
            except Exception, e:
                traceback.print_exc()
                print e
                Log().info(u"new audit apply failed %s" % str(e))
                return HttpResponse(json.dumps({"error" : "failed", "msg": str(e)}))
    return HttpResponse(json.dumps({"error" : "get only", "msg":"get only"}))

@csrf_exempt
def download_table1(request):
    if request.method == 'GET':
        Log().info("download table1")
        repayments = FundDetailDataProvider().object_filter(request)
        try :
            w = Workbook()
            ws = w.add_sheet('table1-%s' % datetime.now().strftime("%y-%m-%d"))
            i = 0
            fnt = Font()
            fnt.name = 'Arial'
            fnt.colour_index = 4
            fnt.bold = True
            fnt.height = 14*0x14
            align = Alignment()
            align.horz = Alignment.HORZ_CENTER
            title_style = XFStyle()
            title_style.font = fnt
            title_style.alignment = align
            if True:
                i += 1
                ws.write(i, 0, unicode("渠道", 'utf-8'))
                ws.write(i, 1, unicode("合同号", 'utf-8'))
                ws.write(i, 2, unicode("姓名", 'utf-8'))
                ws.write(i, 3, unicode("类型", 'utf-8'))
                ws.write(i, 4, unicode("身份证号", 'utf-8'))
                ws.write(i, 5, unicode("借款金额", 'utf-8'))
                ws.write(i, 6, unicode("本金", 'utf-8'))
                ws.write(i, 7, unicode("期数", 'utf-8'))
            #    ws.write(i, 8, unicode("利息", 'utf-8'))
            #    ws.write(i, 9, unicode("服务费", 'utf-8'))
                ws.write(i, 8, unicode("总应还", 'utf-8'))
                ws.write(i, 9, unicode("泰康", 'utf-8'))
                ws.write(i, 10, unicode("放款日期", 'utf-8'))
            for repay in repayments:
                i += 1
                ws.write(i, 0,unicode(repay.get_capital_channel_id_display()))
                ws.write(i, 1,unicode(repay.order_number))
                ws.write(i, 2,unicode(repay.user.name))
                ws.write(i, 3,unicode(Profile.objects.get(owner=repay.user).get_job_display()))
                ws.write(i, 4,unicode(repay.user.id_no))
                ws.write(i, 5,unicode(repay.apply_amount/100.0))
                ws.write(i, 6,unicode(get_corpus_from_repayment(repay)))
                ws.write(i, 7,unicode(repay.get_strategy_id_display()))
            #    ws.write(i, 8,unicode(repay.apply_amount/100.0))
            #    ws.write(i, 9,unicode(repay.apply_amount/100.0))
                ws.write(i, 8,unicode(repay.repay_amount/100.0))
                ws.write(i, 9,unicode(get_taikang_repayment(repay)))
                ws.write(i, 10,unicode(repay.first_repay_day.strftime("%Y-%m-%d")))
            w.save('s.xls')
        except Exception, e:
            print "excp", e
            traceback.print_exc()
            return HttpResponse(json.dumps({"error" : u"load failed"}))
        response = StreamingHttpResponse(FileWrapper(open('s.xls'), 8192), content_type='application/vnd.ms-excel')
        response['Content-Length'] = os.path.getsize("s.xls")
        response['Content-Disposition'] = 'attachment; filename=%s.xls' % '资金明细-%s' % datetime.now().strftime("%y-%m-%d")
        return response

@csrf_exempt
def download_table2(request):
    if request.method == 'GET':
        pass

@csrf_exempt
def download_table4(request):
    if request.method == 'GET':
        pass

@csrf_exempt
def export_repay_loan_table(request):
    if request.method == 'GET':
        Log().info("download export_repay_loan_table")
        query_set = RepayLoanDataProvider().object_filter(request)
        result_set = []
        if query_set:
            result_set = RepayLoanDataProvider().fill_data(query_set)
        try:
            w = Workbook()
            ws = w.add_sheet(u'代扣-%s' % datetime.now().strftime("%y-%m-%d"))
            i = 0
            fnt = Font()
            fnt.name = 'Arial'
            fnt.colour_index = 4
            fnt.bold = True
            fnt.height = 14*0x14
            align = Alignment()
            align.horz = Alignment.HORZ_CENTER
            title_style = XFStyle()
            title_style.font = fnt
            title_style.alignment = align
            if True:
                i += 1
                ws.write(i, 0, unicode("id", 'utf-8'))
                ws.write(i, 1, unicode("订单号", 'utf-8'))
                ws.write(i, 2, unicode("用户", 'utf-8'))
                ws.write(i, 3, unicode("身份证", 'utf-8'))
                ws.write(i, 4, unicode("借款金额", 'utf-8'))
                ws.write(i, 5, unicode("到账金额", 'utf-8'))
                ws.write(i, 6, unicode("借贷方式", 'utf-8'))
                ws.write(i, 7, unicode("银行名称", 'utf-8'))
                ws.write(i, 8, unicode("申请时间", 'utf-8'))
                ws.write(i, 9, unicode("起息日", 'utf-8'))
                ws.write(i, 10, unicode("状态", 'utf-8'))
                ws.write(i, 11, unicode("当前期数", 'utf-8'))
            #    ws.write(i, 8, unicode("利息", 'utf-8'))
            #    ws.write(i, 9, unicode("服务费", 'utf-8'))
            for data in result_set:
                i += 1
                ws.write(i,0,data["id"])
                ws.write(i,1,data["order_number"])
                ws.write(i,2,data["name"])
                ws.write(i,3,data["card_id"])
                ws.write(i,4,data["amount"])
                ws.write(i,5,data["repay_amount"])
                ws.write(i,6,data["strategy"])
                ws.write(i,7,data["bank_data"])
                ws.write(i,8,data["apply_time"])
                ws.write(i,9,data["getpay_time"])
                ws.write(i,10,data["status"])
                ws.write(i,11,data["current_peroids"])
            w.save('s.xls')
        except Exception, e:
            print "excp", e
            traceback.print_exc()
            return HttpResponse(json.dumps({"error" : u"load failed"}))
        response = StreamingHttpResponse(FileWrapper(open('s.xls'), 8192), content_type='application/vnd.ms-excel')
        response['Content-Length'] = os.path.getsize("s.xls")
        response['Content-Disposition'] = 'attachment; filename=%s.xls' % '代扣-%s' % datetime.now().strftime("%y-%m-%d")
        return response

@csrf_exempt
def export_pay_loan_table(request):
    if request.method == 'GET':
        Log().info("download export_pay_loan_table")
        query_set = PayLoanDataProvider().object_filter(request)
        result_set = PayLoanDataProvider().fill_data(query_set)
        try :
            w = Workbook()
            ws = w.add_sheet(u'代付-%s' % datetime.now().strftime("%y-%m-%d"))
            i = 0
            fnt = Font()
            fnt.name = 'Arial'
            fnt.colour_index = 4
            fnt.bold = True
            fnt.height = 14*0x14
            align = Alignment()
            align.horz = Alignment.HORZ_CENTER
            title_style = XFStyle()
            title_style.font = fnt
            title_style.alignment = align
            if True:
                i += 1
                ws.write(i, 0, unicode("申请id", 'utf-8'))
                ws.write(i, 1, unicode("订单号", 'utf-8'))
                ws.write(i, 2, unicode("渠道", 'utf-8'))
                ws.write(i, 3, unicode("用户", 'utf-8'))
                ws.write(i, 4, unicode("身份证", 'utf-8'))
                ws.write(i, 5, unicode("借款金额", 'utf-8'))
                ws.write(i, 6, unicode("到账金额", 'utf-8'))
                ws.write(i, 7, unicode("借贷方式", 'utf-8'))
                ws.write(i, 8, unicode("申请时间", 'utf-8'))
                ws.write(i, 9, unicode("起息日", 'utf-8'))
                ws.write(i, 10, unicode("状态", 'utf-8'))
                ws.write(i, 11, unicode("米饭打款状态", 'utf-8'))
            #    ws.write(i, 8, unicode("利息", 'utf-8'))
            #    ws.write(i, 9, unicode("服务费", 'utf-8'))
            for data in result_set:
                i += 1
                ws.write(i,0,data["id"])
                ws.write(i,1,data["order_number"])
                ws.write(i,2,data["channel"])
                ws.write(i,3,data["name"])
                ws.write(i,4,data["card_id"])
                ws.write(i,5,data["amount"])
                ws.write(i,6,data["repay_amount"])
                ws.write(i,7,data["strategy"])
                ws.write(i,8,data["apply_time"])
                ws.write(i,9,data["getpay_time"])
                ws.write(i,10,data["status"])
                ws.write(i,11,data["mifan_status"])
            w.save('s.xls')
        except Exception, e:
            print "excp", e
            traceback.print_exc()
            return HttpResponse(json.dumps({"error" : u"load failed"}))
        response = StreamingHttpResponse(FileWrapper(open('s.xls'), 8192), content_type='application/vnd.ms-excel')
        response['Content-Length'] = os.path.getsize("s.xls")
        response['Content-Disposition'] = 'attachment; filename=%s.xls' % '代付-%s' % datetime.now().strftime("%y-%m-%d")
        return response
@csrf_exempt
def download_table3(request):
    if request.method == 'GET':
        Log().info("download table3")
        query_set = OverDueDetail_sum_Provider().object_filter(request)
        try:
            w = Workbook()
            ws = w.add_sheet('table3-%s' % datetime.now().strftime("%y-%m-%d"))
            i = 0
            fnt = Font()
            fnt.name = 'Arial'
            fnt.colour_index = 4
            fnt.bold = True
            fnt.height = 14*0x14
            align = Alignment()
            align.horz = Alignment.HORZ_CENTER
            title_style = XFStyle()
            title_style.font = fnt
            title_style.alignment = align
            if True:
                i += 1
                ws.write(i, 0, unicode("渠道", 'utf-8'))
                ws.write(i, 1, unicode("订单号", 'utf-8'))
                ws.write(i, 2, unicode("姓名", 'utf-8'))
                ws.write(i, 3, unicode("类型", 'utf-8'))
                ws.write(i, 4, unicode("身份证号", 'utf-8'))
                ws.write(i, 5, unicode("借款金额", 'utf-8'))
                ws.write(i, 6, unicode("期数", 'utf-8'))
                ws.write(i, 7, unicode("还款期数", 'utf-8'))
                ws.write(i, 8, unicode("应还日期", 'utf-8'))
                ws.write(i, 9, unicode("每期应还", 'utf-8'))
                ws.write(i, 10, unicode("逾期天数", 'utf-8'))
            #    ws.write(i, 8, unicode("利息", 'utf-8'))
            #    ws.write(i, 9, unicode("服务费", 'utf-8'))
                ws.write(i, 11, unicode("滞纳金", 'utf-8'))
                ws.write(i, 12, unicode("实还金额", 'utf-8'))
                ws.write(i, 13, unicode("代扣笔数", 'utf-8'))
                ws.write(i, 14, unicode("到账金额", 'utf-8'))
                ws.write(i, 15, unicode("手续费", 'utf-8'))
                ws.write(i, 16, unicode("还款方式", 'utf-8'))
                ws.write(i, 17, unicode("逾期状态", 'utf-8'))
                ws.write(i, 18, unicode("实还日期", 'utf-8'))
                ws.write(i, 19, unicode("减免金额", 'utf-8'))
                ws.write(i, 20, unicode("实际到账滞纳金", 'utf-8'))
            for install in query_set:
                repay = install.repayment
                i += 1
                ws.write(i, 0,unicode(repay.get_capital_channel_id_display()))
                ws.write(i, 1,unicode(str(repay.order_number)))
                ws.write(i, 2,unicode(repay.user.name))
                ws.write(i, 3,unicode(Profile.objects.get(owner=repay.user).get_job_display()))
                ws.write(i, 4,unicode(repay.user.id_no))
                ws.write(i, 5,unicode(repay.apply_amount/100.0))
                ws.write(i, 6,unicode(get_periods_from_repayment(repay)))
                ws.write(i, 7,unicode(install.installment_number))
                ws.write(i, 8,unicode(str(install.should_repay_time)))
                ws.write(i, 9,unicode(install.should_repay_amount/100.0))
                ws.write(i, 10,unicode(get_over_due_days(install)))
                ws.write(i, 11,unicode(install.repay_overdue/100.0))
                ws.write(i, 12,unicode(install.real_repay_amount/100.0))
                ws.write(i, 13,unicode(get_installment_repay_count(install)))
                ws.write(i, 14,unicode(install.real_repay_amount/100.0 - int(get_installment_repay_count(install))))
                ws.write(i, 15,unicode(2 - int(get_installment_repay_count(install))))
                ws.write(i, 16,unicode(get_installment_repay_type_count(install)))
                ws.write(i, 17,unicode(install.get_repay_status_display()))
                ws.write(i, 18,unicode(str(install.real_repay_time)))
                ws.write(i, 19,unicode((install.reduction_amount)/100.0))
                ws.write(i, 20,unicode((install.repay_overdue - install.reduction_amount)/100.0))
            w.save('s.xls')
        except Exception, e:
            print "excp", e
            traceback.print_exc()
            return HttpResponse(json.dumps({"error" : u"load failed"}))
        response = StreamingHttpResponse(FileWrapper(open('s.xls'), 8192), content_type='application/vnd.ms-excel')
        response['Content-Length'] = os.path.getsize("s.xls")
        response['Content-Disposition'] = 'attachment; filename=%s.xls' % '未还明细-%s' % datetime.now().strftime("%y-%m-%d")
        return response

@csrf_exempt
def download_pay_loan(request):
    if request.method == 'GET':
        aids = request.GET.get("aid")
        channel = request.GET.get("type")
        Log().info("download pay_loan %s %s" % (aids, channel))
        aid_list = aids.split(',')
        try :
            applys = Apply.objects.filter(Q(id__in = aid_list))
            #repayments = RepaymentInfo.objects.filter(Q(id__in = aid_list))
            w = Workbook()
            ws = w.add_sheet('pay_list-%s' % datetime.now().strftime("%y-%m-%d"))
            i = 0

            fnt = Font()
            fnt.name = 'Arial'
            fnt.colour_index = 4
            fnt.bold = True
            fnt.height = 14*0x14
            align = Alignment()
            align.horz = Alignment.HORZ_CENTER
            title_style = XFStyle()
            title_style.font = fnt
            title_style.alignment = align

            if channel == 'xintuo':
                ws.write_merge(0, 0, 0, 19, unicode("信托资金划拨明细", "utf-8"), title_style)
                # TODO: 这里性能可能有问题
                i += 1
            i = 0

            fnt = Font()
            fnt.name = 'Arial'
            fnt.colour_index = 4
            fnt.bold = True
            fnt.height = 14*0x14
            align = Alignment()
            align.horz = Alignment.HORZ_CENTER
            title_style = XFStyle()
            title_style.font = fnt
            title_style.alignment = align

            if channel == 'xintuo':
                ws.write_merge(0, 0, 0, 19, unicode("信托资金划拨明细", "utf-8"), title_style)
                # TODO: 这里性能可能有问题
                i += 1
                ws.write(i, 0, unicode("序号", 'utf-8'))
                ws.write(i, 1, unicode("合同号", 'utf-8'))
                ws.write(i, 2, unicode("户名", 'utf-8'))
                ws.write(i, 3, unicode("身份证号", 'utf-8'))
                ws.write(i, 4, unicode("贷款本金", 'utf-8'))
                ws.write(i, 5, unicode("贷款金额", 'utf-8'))
                ws.write(i, 6, unicode("借款金额", 'utf-8'))
                ws.write(i, 7, unicode("日贷款服务费", 'utf-8'))
                ws.write(i, 8, unicode("日利率", 'utf-8'))
                ws.write(i, 9, unicode("贷款天数", 'utf-8'))
                ws.write(i, 10, unicode("还款期数", 'utf-8'))
                ws.write(i, 11, unicode("每期还款金额", 'utf-8'))
                ws.write(i, 12, unicode("借款账号", 'utf-8'))
                ws.write(i, 13, unicode("开户银行", 'utf-8'))
                ws.write(i, 14, unicode("开户支行", 'utf-8'))
                ws.write(i, 15, unicode("还款账号", 'utf-8'))
                ws.write(i, 16, unicode("开户银行", 'utf-8'))
                ws.write(i, 17, unicode("开户支行", 'utf-8'))
                for apply in applys:
                    i += 1
                    repayment = apply.repayment
                    #contracts = Contract.objects.filter(owner = repayment.user).order_by("-sign_time")
                    #order_id = contracts[0].contract_id if len(contracts) == 1 else ""
                    ws.write(i, 0, i+1)
                    ws.write(i, 1, repayment.order_number)
                    ws.write(i, 2, repayment.user.name)
                    ws.write(i, 3, repayment.user.id_no)
                    ws.write(i, 4, repayment.apply_amount/100.0)
                    ws.write(i, 5, repayment.apply_amount*(1 - 0.0003 * repayment.get_repayments_days())/100.0)
                    ws.write(i, 6, repayment.exact_amount/100.0)
                    ws.write(i, 7, "%.2f%%" % repayment.get_strategy_rate())
                    ws.write(i, 8, "0.03%")
                    ws.write(i, 9, repayment.get_repayments_days())
                    ws.write(i, 10, repayment.get_repayments_instalments())
                    ws.write(i, 11, repayment.get_first_installments_amount()/100.0)
                    ws.write(i, 12, repayment.bank_card.card_number)
                    ws.write(i, 13, repayment.bank_card.get_bank_type_display())
                    ws.write(i, 14, "")
                    ws.write(i, 15, repayment.bank_card.card_number)
                    ws.write(i, 16, repayment.bank_card.get_bank_type_display())
                    ws.write(i, 17, "")
                    if apply.status == '0':
                        apply.status = '1'
                        apply.save()
            elif channel == 'mifan':
                ws.write_merge(0, 0, 0, 19, unicode("米饭P2P资金划拨明细", "utf-8"), title_style)
                i += 1
                ## 哦 新版本
                ws.write(i, 0, unicode("状态", 'utf-8'))
                ws.write(i, 1, unicode("标识", 'utf-8'))
                ws.write(i, 2, unicode("申请单号", 'utf-8'))
                ws.write(i, 3, unicode("还款人户名", 'utf-8'))
                ws.write(i, 4, unicode("还款人证件号", 'utf-8'))
                ws.write(i, 5, unicode("还款人银行卡号", 'utf-8'))
                ws.write(i, 6, unicode("还款银行", 'utf-8'))
                ws.write(i, 7, unicode("审批金额", 'utf-8'))
                ws.write(i, 8, unicode("还款人电话", 'utf-8'))
                ws.write(i, 9, unicode("审批期限", 'utf-8'))
                ws.write(i, 10, unicode("产品号", 'utf-8'))
                ws.write(i, 11, unicode("每期还款", 'utf-8'))
                ws.write(i, 12, unicode("收款人名称", 'utf-8'))
                ws.write(i, 13, unicode("收款银行", 'utf-8'))
                ws.write(i, 14, unicode("收款支行", 'utf-8'))
                ws.write(i, 15, unicode("收款银行卡号", 'utf-8'))
                ws.write(i, 16, unicode("收款银行开户省", 'utf-8'))
                ws.write(i, 17, unicode("收款开户行市", 'utf-8'))
                ws.write(i, 18, unicode("收款银行卡类型", 'utf-8'))
                ws.write(i, 19, unicode("申请日期", 'utf-8'))
                for apply in applys:
                    i += 1
                    repayment = apply.repayment
                    s = Strategy.objects.get(pk = repayment.strategy_id)
                    #print s.get_installment_amount(repayment.apply_amount, 1)
                    #contracts = Contract.objects.filter(owner = repayment.user).order_by("-sign_time")
                    #order_id = contracts[0].contract_id if len(contracts) == 1 else ""
                    ws.write(i, 0, 0)
                    ws.write(i, 1, unicode("rst", 'utf-8'))
                    ws.write(i, 2, repayment.order_number)
                    ws.write(i, 3, repayment.user.name)
                    ws.write(i, 4, repayment.user.id_no)
                    ws.write(i, 5, repayment.bank_card.card_number)
                    ws.write(i, 6, repayment.bank_card.get_bank_type_display())
                    ws.write(i, 7, repayment.apply_amount/100.0)
                    ws.write(i, 8, repayment.user.phone_no)
                    ws.write(i, 9, s.installment_days if s.is_day_percentage() else s.installment_count)
                    ws.write(i, 10, '1' if s.is_day_percentage() else "0")
                    ws.write(i, 11, s.get_installment_amount(repayment.apply_amount, 1)/100.0)
                    ws.write(i, 12, repayment.user.name)
                    ws.write(i, 13, repayment.bank_card.get_bank_type_display())
                    ws.write(i, 14, repayment.bank_card.bank)
                    ws.write(i, 15, repayment.bank_card.card_number)
                    ws.write(i, 16, repayment.bank_card.bank_province)
                    ws.write(i, 17, repayment.bank_card.bank_city)
                    ws.write(i, 18, "0")
                    ws.write(i, 19, repayment.apply_time.strftime("%Y-%m-%d %H:%M:%S") )
                    # 已经有了米饭请款接口,不需要再用以前的接口了，保留这个运营方便倒表
                    #if apply.status == '0':
                    #    apply.status = '1'
                    #    apply.save()
            w.save('s.xls')
        except Exception, e:
            print "excp", e
            traceback.print_exc()
            return HttpResponse(json.dumps({"error" : u"load failed"}))
        response = StreamingHttpResponse(FileWrapper(open('s.xls'), 8192), content_type='application/vnd.ms-excel')
        response['Content-Length'] = os.path.getsize("s.xls")
        response['Content-Disposition'] = 'attachment; filename=%s.xls' % 'pay_list-%s' % datetime.now().strftime("%y-%m-%d")
        return response
    return HttpResponse(json.dumps({"error" : "get only"}))

#@csrf_exempt
#def gen_excel(request):
#    if request.method == 'GET':
#        try :
#            w = Workbook()
#            ws = w.add_sheet('100个最近拒绝的用户-%s' % datetime.now().strftime("%y-%m-%d"))
#            i = 0
#            fnt = Font()
#            fnt.name = 'Arial'
#            fnt.colour_index = 4
#            fnt.bold = True
#            fnt.height = 14*0x14
#            align = Alignment()
#            align.horz = Alignment.HORZ_CENTER
#            title_style = XFStyle()
#            title_style.font = fnt
#            title_style.alignment = align
#
#            #repaymentinfo = RepaymentInfo.objects.get(id= 366)
#            #repay_temp_dict = repaymentinfo.get_repay_status_display()
#            #print  "########"
#            #print  repay_temp_dict
#            repay_status_type_t = {
#                0: '放款中',
#                1: '还款中',
#                2: '逾期',
#                3: '已完成',
#                4: '审核中',
#                5: '已放款',
#                6: '审核通过',
#                7: '---',
#                8: '逾期完成',
#            }
#            i += 1
#           # ws.write(i, 0, unicode("用户id", 'utf-8'))
#           # ws.write(i, 1, unicode("名字", 'utf-8'))
#           # ws.write(i, 2, unicode("银行卡", 'utf-8'))
#            ws.write(i, 0, unicode("用户id", 'utf-8'))
#            ws.write(i, 1, unicode("logid", 'utf-8'))
#            ws.write(i, 2, unicode("时间", 'utf-8'))
#            #ws.write(i, 0, unicode("用户id", 'utf-8'))
#            #ws.write(i, 1, unicode("用户名", 'utf-8'))
#            #ws.write(i, 2, unicode("状态", 'utf-8'))
#            #ws.write(i, 3, unicode("订单号", 'utf-8'))
#            id_list = [442,452]
#            #items = Apply.objects.filter(Q(id__in = id_list))
#            #items = Apply.objects.filter(Q(id = 442))
#            cursor = connection.cursor()
#            #cursor.execute("select user.id ,name , bankcard.number FROM user RIGHT JOIN bankcard   ON  user.id =  bankcard.user_id limit 250")
#            cursor.execute("select uin ,logid ,timestamp from report  where uin in  ( select id  from user where id > 99792)")
#            #cursor.execute("select owner_id ,  (select name from user where id = owner_id )as name  from checkstatus where apply_status =  5 order by id  desc  limit 100")
#            #cursor.execute("select user_id ,(select name from user where id = user_id )as name  ,repay_status , order_number from repaymentinfo where repay_status in (0,1,2,3,5,8)  order by user_id ,id desc limit 200")
#            items = cursor.fetchall()
#            #items = RepaymentInfo.objects.filter(Q(id__in = aid_list))
#            for item in items:
#                i += 1
#                ws.write(i, 0, item[0])
#         #       ws.write(i, 1, item[1])
#               # ws.write(i, 2, item[2])
#                if item[1] in report_table:
#                    ws.write(i, 1, report_table[item[1]])
#                else:
#                    ws.write(i, 1, item[1])
#                timeStamp = int(item[2])
#                dateArray = datetime.utcfromtimestamp(timeStamp)
#                otherStyleTime = dateArray.strftime("%Y-%m-%d %H:%M:%S")
#                ws.write(i, 2, otherStyleTime)
#                #ws.write(i, 2, item[2])
#                #ws.write(i, 2, unicode(repay_status_type_t[int(item[2])], 'utf-8'))
#                #ws.write(i, 3, item[3])
#
#            w.save('s.xls')
#        except Exception, e:
#            print "excp", e
#            traceback.print_exc()
#            return HttpResponse(json.dumps({"error" : u"load failed"}))
#        response = StreamingHttpResponse(FileWrapper(open('s.xls'), 8192), content_type='application/vnd.ms-excel')
#        response['Content-Length'] = os.path.getsize("s.xls")
#        response['Content-Disposition'] = 'attachment; filename=%s.xls' % 'pay_list-%s' % datetime.now().strftime("%y-%m-%d")
#        return response
#    return HttpResponse(json.dumps({"error" : "get only"}))
def get_forword_month_day(start_day=None, i=1):
    if not start_day:
        start_day = datetime.now()
    month = start_day.month - 1 + i
    year = start_day.year + month / 12
    month = month % 12 + 1
    day = min(start_day.day, calendar.monthrange(year,month)[1])
    return datetime(year,month,day)

def get_installment_date(i, day=None,id=10):
    '''
        第i期还款时间(预计)  T+1 + timedelta * i
    '''

    print id
    if id == 10:
        return day + timedelta(21)
    elif id == 11:
        return day + timedelta(28)
    else:
        return get_forword_month_day(day,i )
def test(request):
    print "haha"
    repay = RepaymentInfo.objects.get(order_number = "5479973054617235126")
    install = InstallmentDetailInfo.objects.get(repayment = repay)
    day = get_installment_repay_count(install)
    print day
    return HttpResponse(day)
    return HttpResponse("test")
#    t1 = '2016-2-3'
#    date  = time.strptime(t1,"%Y-%m-%d") #struct_time类型
#    d1 = datetime(date[0], date[1],date[2]) #datetime类型
#    ''' 找出有些还没到还款日期 但是状态 是逾期的 找出这些数据修复'''
#    t2 = '2016-2-16'
#    date  = time.strptime(t2,"%Y-%m-%d") #struct_time类型
#    d2 = datetime(date[0], date[1],date[2]) #datetime类型
#    applys = Apply.objects.filter( Q(status = 'i') & Q(type = 'p'))
#
#    i = 0
#    for apply in applys:
#        apply.status = '0'
#        apply.save()
###        if apply.repayment.repay_status in (3,8):
##        installments = InstallmentDetailInfo.objects.filter(repayment=apply.repayment, installment_number=apply.money + 1)
##        installment = None
##        if len(installments) == 1:
##            installment = installments[0]
##        if installment.should_repay_time > d2:
##            print apply.repayment.user.name, "期数:", apply.money +1 ,installment.should_repay_time
#        i += 1
#    print "conut:", i
#
#    t2 = '2016-2-16'
#    date  = time.strptime(t2,"%Y-%m-%d") #struct_time类型
#    d2 = datetime(date[0], date[1],date[2]) #datetime类型
#    installs =  InstallmentDetailInfo.objects.filter( Q(repay_status = 2))
#    for i in installs:
#        if i.should_repay_amount + i.repay_overdue - i.reduction_amount - i.real_repay_amount == 1:
##        i.repay_overdue = 0
##        i.repay_penalty= 0
##        i.repay_overdue_interest= 0
##        i.repay_status = 7
##        i.save()
##        i.repayment.repay_status = 1
##        i.repayment.next_repay_time = get_forword_month_day(i.repayment.next_repay_time)
##        i.repayment.save()
#            print i.repayment.user.name
#        
       #print a
#    orders = [
#"2098312963114221559",
#"6052040352590615591",
#"7106670789371903058",
#"5995456529668672283",
#"4835657069435688674",
#"1755985544939777472",
#"7273845457579845587",
#"3955328670400589555",
#"6832117447519989567",
#"7440264783410375721"
#]
#
#    for o in orders:
#        r = RepaymentInfo.objects.get(Q(order_number = str(o)))
#        installs =  InstallmentDetailInfo.objects.filter(repayment_id=r.id)
#        for i in installs:
#    #        i.should_repay_time   =  get_installment_date(i.installment_number, r.first_repay_day,r.strategy_id)
#    #        i.save()
#            print r.order_number,r.user.phone_no,r.strategy_id,i.should_repay_time , r.next_repay_time,r.first_repay_day,r.user.name
#            #print a
#
#    applys= Apply.objects.filter(Q(status = '9') & Q(type = 'p'))
#    for apply in applys:
#        collection_applys = Apply.objects.filter(Q(repayment=apply.repayment) & Q(money=apply.money) & Q(type__in=[Apply.COLLECTION_M0, Apply.COLLECTION_M1, Apply.COLLECTION_M2, Apply.COLLECTION_M3, Apply.COLLECTION_M4]))
#        if len(collection_applys) >= 1:
#            collection_apply = collection_applys[0]
#            #if collection_apply.status == Apply.REPAY_SUCCESS:
#            if collection_apply.status == Apply.PROCESSING or collection_apply.status == Apply.REPAY_FAILED:
#            #if collection_apply.status == Apply.PROCESSING and collection_apply.type == Apply.COLLECTION_M0:
#                collection_apply.status = Apply.REPAY_SUCCESS
#                collection_apply.save()
#                print apply.repayment.user.name, apply.money + 1,apply.repayment.order_number ,collection_apply.status,collection_apply.type
    """下面的片段是校验生成扣款 apply 的生成时间是否正确"""
    print "enter"
#    repayments = RepaymentInfo.objects.filter(Q(capital_channel_id = 2) & Q(repay_status__in  = [0])).order_by('first_repay_day')
#    order_numbers = []
#    for r in repayments:
#    #    print r.order_number
#        order_numbers.append(r.order_number)
#    print order_numbers
   
#    applys= Apply.objects.filter( Q(type = 'p') & Q(status = 0))
#    for apply in applys:
#         print apply.money,apply.repayment.user.name, apply.create_at,apply.repayment.order_number, apply.repayment.repay_status
#         apply.delete()
#        for i in InstallmentDetailInfo.objects.filter(Q(repayment = r)):
#            if r.strategy_id == 10 or r.strategy_id == 11:
#                if (i.should_repay_time.day - r.next_repay_time.day) != 0:
#                    print r.order_number,r.user.phone_no,r.strategy_id,i.should_repay_time , r.next_repay_time,r.first_repay_day,r.user.name
#                    #print r.order_number,r.first_repay_day,r.user.name
#            else:
#                if i.should_repay_time.day !=  r.next_repay_time.day:
#                    print r.order_number,r.user.phone_no,r.strategy_id, i.should_repay_time, r.next_repay_time, r.first_repay_day,r.user.name
                    #print r.order_number,r.first_repay_day,r.user.name
#"""下面的片段是查看逾期客户的审批责任人 """
    def get_over_due_days(install):
        if install.real_repay_time == None:
            #return "错误还款时间"
            today  = datetime.now()
            return (datetime.combine(today, datetime.min.time()) - datetime.combine(install.should_repay_time, datetime.min.time())).days
        if install.repay_status == 2:
            today  = datetime.now()
            return (datetime.combine(today, datetime.min.time()) - datetime.combine(install.should_repay_time, datetime.min.time())).days
        elif install.repay_status == 7  or install.repay_status == 3:
            return 0
        elif install.repay_status == 1:
            return 0.
        elif install.repay_status == 8:
            return (datetime.combine(install.real_repay_time, datetime.min.time()) - datetime.combine(install.should_repay_time, datetime.min.time())).days
        else:
            return (datetime.combine(install.real_repay_time, datetime.min.time()) - datetime.should_repay_time.combine(install.should_repay_time, datetime    .min.time())).days
    t1 = '2016-1-01'
    t = time.strptime(t1,"%Y-%m-%d") #struct_time类型
    d1 = datetime(t[0], t[1],t[2]) #datetime类型
    t2 = '2016-2-01'
    date  = time.strptime(t2,"%Y-%m-%d") #struct_time类型
    d2 = datetime(date[0], date[1],date[2]) #datetime类型

    applys= Apply.objects.filter(Q(create_at__gte =  d1) & Q(create_at__lte =  d2)  & Q(type = 'p'))
    print 'query sql: ' + str(applys.query)
    print applys.count()
    user_list = {}
    for apply in applys:
        collection_applys = Apply.objects.filter(Q(repayment=apply.repayment) & Q(money=apply.money) & Q(type__in=[Apply.COLLECTION_M1, Apply.COLLECTION_M2, Apply.COLLECTION_M3, Apply.COLLECTION_M4]))
        if len(collection_applys) >= 1:
            collection_apply = collection_applys[0]
            print apply.repayment.user.id
            install = InstallmentDetailInfo.objects.get(Q(repayment = apply.repayment) & Q(installment_number = (apply.money + 1)))
            user_list[int(apply.repayment.user.id)] = get_over_due_days(install)
    print user_list
#            #if collection_apply.status == Apply.REPAY_SUCCESS:
#            if  collection_apply.status == Apply.REPAY_FAILED:
#            #if collection_apply.status == Apply.PROCESSING or collection_apply.status == Apply.REPAY_FAILED:
#            #if collection_apply.status == Apply.PROCESSING and collection_apply.type == Apply.COLLECTION_M0:
#                #collection_apply.status = Apply.REPAY_SUCCESS
#                #collection_apply.save()
#                #print apply.repayment.user.id, apply.repayment.user.name, apply.money + 1,apply.repayment.order_number ,collection_apply.status,collection_apply.type
#        if len(collection_applys) >= 1:
#            collection_apply = collection_applys[0]
#            #if collection_apply.status == Apply.REPAY_SUCCESS:
#            if  collection_apply.status == Apply.REPAY_FAILED:
#            #if collection_apply.status == Apply.PROCESSING or collection_apply.status == Apply.REPAY_FAILED:
#            #if collection_apply.status == Apply.PROCESSING and collection_apply.type == Apply.COLLECTION_M0:
#                #collection_apply.status = Apply.REPAY_SUCCESS
#                #collection_apply.save()
#                #print apply.repayment.user.id, apply.repayment.user.name, apply.money + 1,apply.repayment.order_number ,collection_apply.status,collection_apply.type
#                print apply.repayment.user.id
#                user_list.append(apply.repayment.user.id)
#    print user_list
    #    #    print i.repayment.order_number
    return HttpResponse("test")
