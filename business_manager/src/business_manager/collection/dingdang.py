# -*- coding: utf-8 -*-
from django.conf import settings
from django.http import HttpResponse, JsonResponse

import traceback
from pyExcelerator import *
from datetime import datetime
from business_manager.util.permission_decorator import page_permission
from business_manager.order.apply_models import Apply, CheckApply
from business_manager.util.tkdate import *
from business_manager.collection.models import *
from business_manager.python_common.log_client import CommonLog as Log
from django.views.decorators.csrf import csrf_exempt
from business_manager.review.models import *
from business_manager.review import message_client, bank_client, risk_client, redis_client
import requests
import time
import redis
import simplejson
from business_manager.review.employee_models import Employee
from django.shortcuts import get_object_or_404

def apply_trans_status(apply, record):

    # 未分配: 不上报 催记
    if apply.status in ['i']:
        apply.status = Apply.COLLECTION
        apply.save()

        report_data_collection_money(apply)
        apply.update_at = datetime.now()

    if apply.status in ['i', 'ci', 'd', '8', '9']:
        report_data_collection_money(apply, "催记")

    # apply.status = Apply.COLLECTION
    # 未受理订单发送短信改为已受理
    if record.record_type == CollectionRecord.MESSAGE and apply.status in (Apply.WAIT, ):
        apply.status = Apply.COLLECTION
        apply.save()

    apply.collection_record_time = record.create_at
    promised_repay_time = record.promised_repay_time
    if promised_repay_time:
        apply.promised_repay_time = promised_repay_time
    apply.save()


def __Sting2Time(s):
    d = datetime.strptime(s,"%Y-%m-%d %H:%M:%S")
    return time.mktime(d.timetuple())

def __report_data(phone_num, in_out, request, redis_apply_id):
    s = requests.get(r'http://120.26.139.170:29002/httpService/callLog?startDate=&endDate=&callType=3&phoneNo=%s&page=1&pageSize=1'%phone_num)
    json_data = simplejson.loads(s.text).get("rows")[0]
    call_id = redis_client.get(json_data.get("call_accept"))
    # if call_id:
        # redis_client.expire(call_id, 5*60)
    Log().info("json data: %s"%(json_data))
    created_time = __Sting2Time(json_data.get("created_time"))
    answered_time = json_data.get("answered_time").strip()
    over_time = __Sting2Time(json_data.get("over_time"))

    call_duration = 0
    is_connected = "F"
    wait_time = over_time - created_time
    if answered_time:
        answered_time = __Sting2Time(json_data.get("answered_time"))
        call_duration =  over_time - answered_time
        is_connected = "T"
        wait_time = answered_time - created_time

    redis_client_1 = redis.StrictRedis(host="3d5ce3962104443f.m.cnhza.kvstore.aliyuncs.com",port=6379,password="3d5ce3962104443f:Rongshu1234",db=4)
    client = BusinessDataReportClient('10.168.33.117', 8800, redis_client_1, None)
    if in_out == "inbound":
        call_type = 'in'
    if in_out == "outbound":
        call_type = "out"
    staff = Employee.objects.get(phone_no=json_data.get("caller_id_number"))
    collect_type = {"a":"m0","b":"m1","c":"m2","d":"m3","e":"m4","g":"m5","h":"m5+"}
    if redis_apply_id == "":
        data = {
                "measurement":"call_report",
                "time":int(time.time()*10**9),
                "tags":{
                    "org_account":"dingdang",
                    "collector_id":staff.user.username,
                    "is_connected":is_connected,
                    "call_type":call_type,
                    "collection_type":""
                    },
                "fields":{
                    "call_duration":int(call_duration),
                    "apply_id":redis_apply_id,
                    "wait_time":int(wait_time)
                    }
                }
        Log().info("report data: %s"%(data))
        Log().info("user name data: %s"%(staff.user))
        result = client.report_data(json.dumps(data,ensure_ascii=False).encode('utf-8'))
        print result
    elif redis_apply_id != "":
        data = {
                "measurement":"call_report",
                "time":int(time.time()*10**9),
                "tags":{
                    "org_account":"dingdang",
                    "collector_id":staff.user.username,
                    "is_connected":is_connected,
                    "call_type":call_type,
                    "collection_type":collect_type[Apply.objects.get(id=redis_apply_id).type]
                    },
                "fields":{
                    "call_duration":int(call_duration),
                    "apply_id":redis_apply_id,
                    "wait_time":int(wait_time)
                    }
                }
        Log().info("report data: %s"%(data))
        Log().info("user name data: %s"%(staff.user))
        result = client.report_data(json.dumps(data,ensure_ascii=False).encode('utf-8'))
        print result

@csrf_exempt
def report_conversation_data(request):
    if request.method == "GET":
        try:
            phone_num = request.GET.get('phone_num')
            apply_id = request.GET.get('apply_id')
            in_out = request.GET.get('in_out')
            person_num = request.GET.get('person_num')
            raw_data = request.GET.get('raw_data')
            raw_data_dict = json.loads(raw_data)
            report_type = request.GET.get('type')
            call_accept_id = request.GET.get('call_accept')


            call_accept_id_key = "call_id_%s"%(call_accept_id)
            if report_type == 'report_call_id':
                redis_apply_id = redis_client.get(call_accept_id_key)
                if redis_apply_id:
                    return HttpResponse("done")
                redis_client.set(call_accept_id_key, apply_id)
                return HttpResponse("done")
            r = redis_client.pipeline()
            r.get(call_accept_id_key)
            r.delete(call_accept_id_key)
            redis_apply_id = r.execute()[0]
            Log().info("apply id and call id: %s--------%s"%(redis_apply_id, call_accept_id_key))
            if raw_data_dict["call_direction"] == "inbound":
                __report_data(phone_num, in_out, request, "")
                return HttpResponse("ok")
            elif redis_apply_id and raw_data_dict["call_direction"] == "outbound":
                __report_data(phone_num, in_out, request, redis_apply_id)
                return HttpResponse("ok")
        except:
            traceback.print_exc()


@csrf_exempt
def report_callin_conversation(request):
    if request.method == "GET":
        try:
            phone_num = request.GET.get('phone_num')
            apply_id = request.GET.get('apply_id')
            in_out = request.GET.get('in_out')
            person_num = request.GET.get('person_num')
            raw_data = request.GET.get('raw_data')
            raw_data_dict = json.loads(raw_data)
            report_type = request.GET.get('type')
            call_accept_id = request.GET.get('call_accept')

            s = requests.get(r'http://120.26.139.170:29002/httpService/callLog?startDate=&endDate=&callType=3&phoneNo=%s&page=1&pageSize=1'%phone_num)
            json_data = simplejson.loads(s.text).get("rows")[0]

            created_time = __Sting2Time(json_data.get("created_time"))
            answered_time = json_data.get("answered_time").strip()
            over_time = __Sting2Time(json_data.get("over_time"))

            call_duration = 0
            is_connected = "F"
            wait_time = over_time - created_time
            if answered_time:
                answered_time = __Sting2Time(json_data.get("answered_time"))
                call_duration =  over_time - answered_time
                is_connected = "T"
                wait_time = answered_time - created_time

            redis_client_1 = redis.StrictRedis(host="3d5ce3962104443f.m.cnhza.kvstore.aliyuncs.com",port=6379,password="3d5ce3962104443f:Rongshu1234",db=4)
            client = BusinessDataReportClient('10.168.33.117', 8800, redis_client_1, None)
            if in_out == "inbound":
                call_type = 'in'
            staff = get_employee(request)
            # collect_type = {"a":"m0","b":"m1","c":"m2","d":"m3","e":"m3+","e":"m4","g":"m5","h":"m5+"}
            data = {
                    "measurement":"call_report",
                    "time":int(time.time()*10**9),
                    "tags":{
                        "org_account":"dingdang",
                        "collector_id":staff.user.username,
                        "is_connected":is_connected,
                        "call_type":call_type,
                        "collection_type":""
                        },
                    "fields":{
                        "call_duration":int(call_duration),
                        "apply_id": "",
                        "wait_time":int(wait_time)
                        }
                    }
            Log().info("report call in data: %s"%(data))
            Log().info("user name data: %s"%(staff.user))
            result = client.report_data(json.dumps(data,ensure_ascii=False).encode('utf-8'))
            return HttpResponse("ok")
        except Exception as e:
            Log().error("error :%s"%e)

@csrf_exempt
def report_log(request):
    if request.method == "POST":
        raw_data = request.POST.get("raw_data")
        Log().info("raw log: ****************%s"%(raw_data))
        return HttpResponse("ok")

def _get_collection_info():
    collection_info = {}
    return collection_info

@csrf_exempt
def do_pay_overdue_action(request):
    if request.method == 'GET':
        return HttpResponse(json.dumps({"error" : "ok"}))
    return HttpResponse(json.dumps({"error" : "get only"}))

def _get_installment_by_apply(re_apply):
    repayment = re_apply.repayment
    installments = InstallmentDetailInfo.objects.filter(repayment=repayment, installment_number=re_apply.money + 1)
    installment = None
    if len(installments) == 1:
        installment = installments[0]
    return installment

@csrf_exempt
def do_reduction(request):
    if request.method == 'POST':
        try:
            amount = request.POST.get("amount")
            reason = request.POST.get("reason")
            print "reason", reason
            if not reason:
                return HttpResponse(json.dumps({"error" : u"请填写减免原因"}))
            aid = request.POST.get("apply")
            collection_apply = Apply.objects.get(id=int(aid))
            installment = _get_installment_by_apply(collection_apply)
            reduction_amount = int(round(float(amount) * 100))
            radio = 1 if is_collection_manager(request) else 0.4
            if reduction_amount >= 0 and reduction_amount <= installment.repay_overdue * radio:
                installment.reduction_amount = reduction_amount
                installment.save()
                record = CollectionRecord(record_type=CollectionRecord.DISCOUNT, object_type=CollectionRecord.SELF, create_by = get_employee(request),
                        collection_note="减免金额:%s,  减免原因:%s" % (amount, reason), promised_repay_time=None, apply=collection_apply)
                record.save()
                apply_trans_status(collection_apply, record)
                # collection_apply.status = Apply.COLLECTION
                # collection_apply.collection_record_time = record.create_at
                # collection_apply.save()
                Log().info("do_reduction success amount:%s, staff:%s apply_id:%s" % (amount, get_employee(request).username, aid))
                return HttpResponse(json.dumps({"result" : u"ok"}))
            else:
                Log().info("do_reduction out of range. amount:%s, staff:%s apply_id:%s" % (amount, get_employee(request).username, aid))
                return HttpResponse(json.dumps({"error" : u"减免金额超出权限范围"}))
        except Exception, e:
            print e
            traceback.print_exc()
            Log().info("do_reduction failed excp:%s" % (str(e)))
            return HttpResponse(json.dumps({"error" : u"减免失败"}))
    return HttpResponse(json.dumps({"error" : u"post only"}))


def get_rest_repay_money(apply):
    """apply 对应的应还款金额.

    还款完成时, 返回的是 实际还款金额
    """
    print "in rest_repay_money"
    repayment = apply.repayment
    all_ins = InstallmentDetailInfo.objects.filter(repayment=repayment)
    rest_repay_money = sum([ins.should_repay_amount for ins in all_ins if ins.repay_status == 2]) / 100.0
    if not InstallmentDetailInfo.objects.filter(repayment=repayment, repay_status=2):
        if InstallmentDetailInfo.objects.filter(repayment=repayment, repay_status__in=[3, 8]):
            print "real_repay_amount"
            rest_repay_money = sum([ins.real_repay_amount for ins in all_ins]) / 100.0

    print "out rest_repay_money"
    return rest_repay_money


def apply_trans_duration(apply, ignore_status=False):
    """apply 状态转换之间的耗时"""
    print "in apply_trans_duration"
    if not ignore_status and apply.status not in [Apply.COLLECTION, Apply.COLLECTION_SUCCESS, Apply.REPAY_SUCCESS, Apply.PARTIAL_SUCCESS]:
        return 0

    lastest_update_time = apply.update_at or apply.create_at
    now = datetime.now()
    duration = now - lastest_update_time
    duration = int(duration.total_seconds())

    print "out apply_trans_duration"
    return duration


def collector_login_name(apply):
    """apply 对应的催收人员的 login_name

    返回的是最近的 催收人员.
    """
    print "in collector_login_name"
    login_name = ""
    review = CollectionRecord.objects.filter(apply=apply, record_type=CollectionRecord.DISPATCH).order_by("-id").first()
    if review and apply.status not in ['0']:
        login_name = review.create_by.user.username

    print login_name
    print "out collector_login_name"
    return login_name


def apply_installment_number(apply):
    """apply 对应的期数 count

    apply 没有对应的字段, 所以通过 逾期天数, day_and_numbers 获取
    """
    print "in apply_installment_number"
    day_and_numbers = [
        (150, 6),
        (120, 5),
        (90, 4),
        (60, 3),
        (30, 2),
    ]
    overdue_days = apply.overdue_days
    # apply 对应的期数 count
    installment_count = 1
    installments_numbers = []
    for dn in day_and_numbers:
        day, number = dn
        if overdue_days >= day:
            installment_count = number
            break

    print "installment_count: %s" % installment_count
    installments = InstallmentDetailInfo.objects.filter(repayment=apply.repayment, repay_status__in=[2, 3, 8, 9]).order_by("-id")
    # if not installments:
        # installments = InstallmentDetailInfo.objects.filter(repayment=apply.repayment).order_by("-id")
    overdue_installment_count = installments.count()
    overdue_installments = InstallmentDetailInfo.objects.filter(repayment=apply.repayment, repay_status__in=[2]).order_by("id")
    min_overdue_installment_number = 0
    if overdue_installments.first():
        min_overdue_installment_number = overdue_installments.first().installment_number

    installment_number = installments.first().installment_number
    print "installment_number"
    print installment_number
    print 'min_overdue_installment_number'
    print min_overdue_installment_number
    installments_numbers = range(installment_number - installment_count + 1, installment_number + 1)
    # if overdue_installment_count != installment_count:
        # installment_number = installments.first().installment_number
        # installments_numbers = range(installment_number - installment_count + 1, installment_number + 1)
    # else:
        # # 这个没什么用, 结果是和 上面 一样的.
        # installments_numbers = [ins.installment_number for ins in installments]

    # 返回最早的一期
    print "out apply_installment_number"
    # return ",".join([str(i) for i in installments_numbers])
    # 最小是 0期
    return max(installment_number - installment_count, min_overdue_installment_number, 0)


def report_data_collection_money(apply, status_name="", rest_repay_money=0, recover_date=0):
    print
    print "in report_data_collection_money"
    try:
        apply_type_dic = {
            'a': 'm0',
            'b': 'm1',
            'c': 'm2',
            'd': 'm3',
            'e': 'm4',
            'g': 'm5',
            'h': 'm5+',
        }
        apply_status_dic = {
            '0': u"待分配",
            'i': u"未受理",
            'ci': u"已受理",
            'd': u"部分回款",
            '8': u"已完成",
            '9': u"已完成",
        }
        repayment = apply.repayment
        if not status_name:
            status_name = apply_status_dic.get(apply.status)
            # status_name = apply.get_status_display()
            # if apply.status in ['0', 'i']:
                # status_name = apply_status_dic.get(apply.status)
        print 'dddddddddd'
        print apply.update_at
        print status_name
        print "status_name: %s, update_at: %s " % (status_name, apply.update_at)
        collection_type = apply_type_dic.get(apply.type, apply.type)
        instalment_number = apply_installment_number(apply)

        money = rest_repay_money or get_rest_repay_money(apply)
        ignore_status = False
        if status_name=="流转中":
            ignore_status = True
        spend_time = apply_trans_duration(apply, ignore_status)
        assign_date = int(time.mktime(apply.create_at.timetuple()))
        if recover_date:
            recover_date = int(time.mktime(recover_date.timetuple()))
        fields = dict(
            apply_id=int(apply.id),
            money=money,
            spend_time=spend_time,
            assign_date=assign_date,
            recover_date=recover_date,
        )
        print "fields"
        print fields
        tags = dict(
            org_account="dingdang",
            status=status_name,
            collector_id=collector_login_name(apply),
            collection_type=collection_type,
            instalment_number=instalment_number,
        )
        print "tags"
        print tags

        timestamp = int(time.time() * pow(10, 9))
        data = dict(
            measurement="collection_money",
            time=timestamp,
            tags=tags,
            fields=fields,
        )
        print "collection money"
        print data
        print json.dumps(data)
        response = bi_client.report_data(json.dumps(data,ensure_ascii=False).encode('utf-8'))
        print "report bi server response:"
        print response
        print "out report_data_collection_money"
        print
        return data
    except Exception as e:
        print "report_data_collection_money error:"
        print e


@csrf_exempt
# @page_permission(check_employee)
def send_message(request):
    if request.method == 'POST':
        try:
            phone_no = request.POST.get("phone_no")
            content = request.POST.get("content")
            message_template_id = request.POST.get('message_template_id')

            if len(content) > 180:
                return HttpResponse(json.dumps({"error": u"短信超过180个字符"}))

            if message_template_id:
                message_template = Messagetemplate.objects.get(id=message_template_id)

            aid = request.POST.get("apply")
            repay_apply = Apply.objects.get(id=aid)
            res = message_client.dd_send_message(phone_no, content.encode('utf-8'))
            if res:
                record = CollectionRecord(record_type=CollectionRecord.MESSAGE, object_type=phone_no, create_by=get_employee(request),
                                          collection_note=content, promised_repay_time=None, apply=repay_apply)
                record.save()
                apply_trans_status(repay_apply, record)
                # repay_apply.status = Apply.COLLECTION
                # repay_apply.collection_record_time = record.create_at
                # repay_apply.save()
                Log().info("send message to %s success" % phone_no)
                return HttpResponse(json.dumps({"result" : u"ok"}))
            else:
                Log().info("send message to %s faied" % phone_no)
                return HttpResponse(json.dumps({"error" : u"短信发送失败"}))
        except Exception, e:
            print e
            traceback.print_exc()
            return HttpResponse(json.dumps({"error" : u"load failed"}))
    return HttpResponse(json.dumps({"error" : u"post only"}))

import json

@csrf_exempt
def do_collection_action(request):
    if request.method == 'GET':
        aid = request.GET.get("apply_id")
        channel = request.GET.get("channel")
        type = request.GET.get("type")
        # token = request.GET.get("token")
        # exist_token = redis_client.hget("repay_token",  token)
        # if not exist_token:
        #     ret = redis_client.hsetnx("repay_token", token, 1)
        #     if ret == 0: #token已经存在
        #         Log().info("realtime repay_loan %s duplicate token %s" % (aid, token))
        #         return JsonResponse({"code" : 0, "msg": u"不能重复提交"})
        # else:
        #     Log().info("realtime repay_loan %s duplicate token %s" % (aid, token))
        #     return HttpResponse(json.dumps({"error" : "pass", "msg": "不能重复提交"}))

        apply = get_object_or_404(Apply, id = aid)
        # collection_check = request.GET.get("collection_check")
        # redis_client.hset("collection_check", apply.create_by_id, '%s:%s' % (request.user.id, collection_check))
        repayment = apply.repayment
        installments = InstallmentDetailInfo.objects.filter(repayment=repayment, installment_number=apply.money + 1)
        installment = None
        print "status,", apply.status
        if apply.status == Apply.COLLECTION_SUCCESS or apply.status == Apply.REPAY_SUCCESS:
            print "status,", apply.status
            return HttpResponse(json.dumps({"error" : "failed", "msg": "该扣款已经执行成功，不能重复扣款"}))

        if len(installments) == 1:
            installment = installments[0]
        else:
            return HttpResponse(json.dumps({"error" : "failed", "msg": "未找对应的借款信息"}))

        bank_card = BankCard.get_repay_card(repayment)
        if not bank_card:
            return HttpResponse(json.dumps({"error" : "failed", "msg": "未找到还款银行卡"}))

        #if installment.repay_status == RepaymentInfo.DONE or installment.repay_status == RepaymentInfo.OVERDUE_DONE:
        #    _update_related_repay_apply(apply)
        #    return HttpResponse(json.dumps({"error" : "ok", "msg": "该笔贷款已经还完，不能重复扣款"}))

        #sleep(1)
        if channel == 'realtime_repay':
            # Log().info("realtime repay_loan %s start %s" % (aid, token))
            #res = bank_client.realtime_pay(repayment.exact_amount, bank_card.get_bank_code(), bank_card.number, repayment.user.name, repayment.user.id, 'mifan')
            #TODO: check repay status & amount

            all_repay_money = rest_repay_money = installment.should_repay_amount  - installment.real_repay_amount + installment.repay_overdue - installment.reduction_amount
            real_repay_money = 0
            repay_money = 0
            res = None
            msg = ""

            print 'rest_repay_money: ', rest_repay_money
            if rest_repay_money == 0:
                apply.status = Apply.COLLECTION_SUCCESS
                apply.save()
                return HttpResponse(json.dumps({"error" : "ok", "msg": "扣款已完成"}))
            while(rest_repay_money > 0):
                # if rest_repay_money > settings.PAY["max_per_amount"]:
                #     repay_money = settings.PAY["max_per_amount"]
                # else:
                #     repay_money = rest_repay_money

                #res = bank_client.realtime_pay(repay_money, bank_card.get_bank_code(), bank_card.number, repayment.user.name, repayment.user.id, 'mifan')
                # res = bank_client.realtime_pay(repay_money, bank_card.get_bank_code(), bank_card.number, repayment.user.name, repayment.user.id, 'mifan')
                # res = bank_client.collect(repay_money, repayment.user.id, bank_card.card_number, repayment.user.name, repayment.user.phone_no, bank_card.get_bank_code(), 'mifan', '测试', 1, '', '', 0, repayment.user.id_no, 1)
                # msg = res.err_msg if  res and res.err_msg else ""
                #Log().info(u"repay_for %s %s %s %d %d done %s" % (bank_card.get_bank_code(), bank_card.number, repayment.user.name, repayment.user.id, repay_money, token))
                # Log().info("do realtime repay res:%s msg:%s" % (res.retcode, msg.decode("utf-8")))

                rest_repay_money -= repay_money
                # if res.retcode != 0:
                #     break
                # else:
                #     real_repay_money += repay_money

                print 'real_repay_money: ', real_repay_money
                break
            res = True    
            # if res and res.retcode == 0: #扣款成功
            if res:
                try:
                    if apply.type == Apply.COLLECTION_M0:
                        apply.status = Apply.REPAY_SUCCESS
                    else:
                        apply.status = Apply.COLLECTION_SUCCESS
                    apply.save()

                    repay_applys = Apply.objects.filter(repayment=apply.repayment, type=Apply.REPAY_LOAN, money=installment.installment_number - 1)
                    if len(repay_applys) == 1:
                        repay_apply = repay_applys[0]
                        repay_apply.status = Apply.REPAY_SUCCESS
                        repay_apply.save()
                    else:
                        Log().error("update repay_apply failed count:%d, installment:%d" % (len(repay_applys), installment.installment_number))
                    try:
                        res = risk_client.repay_loan(repayment.order_number, installment.installment_number)
                    except Exception, e:
                        traceback.print_exc()
                        print e
                        return HttpResponse(json.dumps({"error" : "failed", "msg": "扣款已经成功, server过程出错，请联系管理员"}))
                    if res != 0:
                        return HttpResponse(json.dumps({"error" : "failed", "msg": "扣款已经成功, server更新失败，请联系管理员"}))
                    staff = Employee.objects.get(user = request.user)
                    note = u"扣款成功 卡号:%s 金额:%s" % (bank_card.number, real_repay_money/100.0)
                    record = CollectionRecord(record_type=CollectionRecord.REPAY, object_type=CollectionRecord.SELF, create_by = staff,
                                          collection_note=note, promised_repay_time=None, apply=apply)
                    record.save()
                except Exception, e:
                    traceback.print_exc()
                    print e
                    return HttpResponse(json.dumps({"error" : "ok", "msg": "扣款已经成功, 系统更新失败，请联系管理员"}))
                return HttpResponse(json.dumps({"error" : "ok", "msg": "扣款成功"}))
            elif real_repay_money > 0: #部分成功
                try:
                    installment.real_repay_amount += real_repay_money
                    installment.save()
                    apply.status = Apply.PARTIAL_SUCCESS
                    apply.save()
                    staff = Employee.objects.get(user = request.user)
                    note = u"扣款部分成功 卡号:%s 扣款金额:%f 成功金额:%f, 最后一笔失败原因%s" % (bank_card.number, all_repay_money/100.0, real_repay_money/100.0, msg.decode("utf-8"))
                    record = CollectionRecord(record_type=CollectionRecord.REPAY, object_type=CollectionRecord.SELF, create_by = staff,
                                          collection_note=note, promised_repay_time=None, apply=apply)
                    record.save()
                    return HttpResponse(json.dumps({"error" : "ok", "msg": "部分成功"}))
                except Exception, e:
                    traceback.print_exc()
                    Log().error("update apply & record part_success %s" % str(e))
                    return HttpResponse(json.dumps({"error" : "failed", "msg": "扣款部分成功, 系统更新失败，请联系管理员"}))
            else:
                try:
                    apply.status = Apply.REPAY_FAILED #失败
                    apply.save()
                    staff = Employee.objects.get(user = request.user)
                    note = u"扣款失败 卡号:%s 扣款金额:%f 失败原因:%s" % (bank_card.number, all_repay_money/100.0, msg.decode("utf-8"))
                    record = CollectionRecord(record_type=CollectionRecord.REPAY, object_type=CollectionRecord.SELF, create_by = staff,
                                                  collection_note=note, promised_repay_time=None, apply=apply)
                    record.save()
                    return HttpResponse(json.dumps({"error" : "ok", "msg": msg.decode("utf-8")}))
                except Exception, e:
                    traceback.print_exc()
                    Log().error("update apply & record failed %s" % str(e))
                    return HttpResponse(json.dumps({"error" : "failed", "msg": "扣款失败, 系统更新失败，请联系管理员"}))
                apply.status = REPAY_FAILED #失败
                apply.save()
                staff = Employee.objects.get(user = request.user)
                note = u"扣款失败 卡号:%s 失败原因:%s" % (bank_card.number, real_repay_money, msg.decode("utf-8"))
                record = CollectionRecord(record_type=CollectionRecord.REPAY, object_type=CollectionRecord.SELF, create_by = staff,
                                      collection_note=note, promised_repay_time=None, apply=apply)
                record.save()
                return HttpResponse(json.dumps({"error" : "failed", "msg": msg.decode("utf-8")}))
        elif channel == "alipay_repay" or channel == "topublic_repay":
            try:
                url = request.GET.get("url")
                notes = request.GET.get("notes")
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
                    # redis_client.hdel("repay_token",  token)
                    return HttpResponse(json.dumps({"error" : "failed", "msg": "请填写正确的凭证金额"}))
                staff = Employee.objects.get(user_id = request.user.id)
                Log().info("%s submit %s, url:%s, check_amount:%d" % (staff.username, channel, url, check_amount))
                #print check_amount, notes, url
                check_type = CheckApply.CHECK_ALIPAY if channel == "alipay_repay" else CheckApply.CHECK_TOPUBLIC
                check_apply = CheckApply(create_by=staff, money=check_amount, repayment=apply.repayment, status=CheckApply.WAIT, pic=url, type=check_type, notes=notes, repay_apply=apply)
                check_apply.save()
                note = u"提交凭证 金额:%d, 类型：%s" % (request.GET.get("check_amount"), check_apply.get_check_type_display())
                record = CollectionRecord(record_type=CollectionRecord.REPAY, object_type=CollectionRecord.SELF, create_by = staff,
                                      collection_note=note, promised_repay_time=None, apply=apply)
                record.save()
                apply.status = Apply.WAIT_CHECK
                apply.save()
                _update_related_repay_apply(apply, Apply.WAIT_CHECK)

                return HttpResponse(json.dumps({"error" : "ok", "msg": "success"}))
            except Exception, e:
                traceback.print_exc()
                print e
                Log().info(u"new audit apply failed %s" % str(e))
                return HttpResponse(json.dumps({"error" : "failed", "msg": str(e)}))
    return HttpResponse(json.dumps({"error" : "get only", "msg":"get only"}))

