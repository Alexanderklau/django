# -*- coding: utf-8 -*- 
import json
import time
import arrow

from django.conf import settings
from django.db.models.query import QuerySet
from django.db.models import Q
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.utils.translation import ugettext_lazy as _
from django.utils import six

from rest_framework import serializers
from rest_framework.compat import set_rollback
from rest_framework import exceptions, status
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework import pagination
from rest_framework.views import exception_handler
from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from rest_framework.exceptions import APIException

from business_manager.review import data_report_client
from business_manager.review.models import *
from business_manager.order.models import User, BankCard, ContactInfo
from business_manager.order.apply_models import Apply
from business_manager.collection.models import InstallmentDetailInfo, RepaymentInfo, InstallmentRecord
from business_manager.config_center.models import ProfileField, ProfileModule
from business_manager.import_data.models import ImportModule
from business_manager.import_data.models import USING, ACTIVE
from business_manager.import_data.serializers import ImportModuleSerializer, ImportFieldSerializer
from business_manager.review import data_report_client
from business_manager.employee.models import get_employee_platform, Platform
from business_manager.strategy.models import Strategy2
from business_manager.collection.services import add_collection_record, collection_extra_data
from business_manager.import_data.models import ParseFileRecord

from datetime import datetime, timedelta

# def trans_to_user(data):
    # user_center_field = ['string_bank_card_id', 'string_qq', 'string_idcard_front', 'string_company_job', 'string_bank_card_phone', 'string_idcard_reverse', 'string_name', 'string_idcard_no', 'string_family_address', 'string_bank_card_name', 'string_company_phone', 'string_bank_card_username', 'string_email', 'string_company_address', 'string_channel', 'string_phone', 'int32_is_student', 'string_company', 'int32_marriaged', 'string_idcard_hand']

RENEW_FEE = 20 * 100

def trans_to_inner_field(data):
    """将 数据导入 api 字段, 转换为 内置字段.

    import_user_data 会使用到
    data 的嵌套深, 所以 inner_field_dic 每个 k, v 一个逻辑来处理.
    """

    print 'in trans_to_inner_field'

    repayment_field = ['int32_penalty', 'int32_should_repay_amount', 'int32_overdue_interest', 'int32_amount', 'int32_real_repay_amount', 'int32_real_time_should_repay_amount']
    exclude_field = ["int32_installment_count", "int32_installment_number", "string_should_repay_time", "string_real_repay_time", "int32_overdue_days", "int32_penalty", "int32_should_repay_amount", "int32_overdue_interest", "string_order_number", "int32_real_repay_amount", "string_repay_status", 'int32_real_time_should_repay_amount','string_apply_start_time', 'string_apply_end_time']

    inner_field_dic = {
        "user_info": {
            "name": "string_name",
            "phone_no": "string_phone",
            "id_no": "string_idcard_no",
            "channel": "string_channel",
            "string_home_address": "string_home_address",

            "register_time" : "",
            "work_address" : "string_company_address",
            "work_name" : "string_company",
            "work_number" : "string_company_phone",
            "mariage" : "int32_marriaged",
            "email": "string_email",
        },
        "card_info": {
            "card_number" : "string_bank_card_id",
            "card_type" : "",
            "bank_type" : "string_bank_card_name",
            "phone_no" : "",
        },
        "repayment_info":{
            "repayment_id": "string_order_number", 
            "amount": "int32_amount",
            "repay_amount" : "",
            "rest_amount" : "", 
            "installment_count" : "int32_installment_count",
            "apply_time": "",
            "pay_time": "",
        },
        # "installment_info": {
            # "installment_number": "int32_installment_number",
            # "installment_status" : "string_repay_status",
            # "should_pay_amount" : "int32_real_time_should_repay_amount",
            # "overdue_amount" : "",
            # "exact_pay_amount" : 0,# 都写成0好了
            # "overdue_days": "int32_overdue_days",
        # },
        "contact_list": ["relationship", "phone_no", "name", "address"],
    }

    user_info = trans_fields(data['user_info'], inner_field_dic['user_info'])
    card_info = trans_fields(data['card_info'], inner_field_dic['card_info'])
    repayment_info = trans_fields(data['repayment_info'], inner_field_dic['repayment_info'])
    contact_info = []
    inner_contact_info = inner_field_dic['contact_list']
    for contact in data['user_info']['contact_list']:
        contact_info.append([contact.get(k, "") for k in inner_contact_info])

    print '----------'
    print user_info
    print card_info
    print repayment_info
    print contact_info
    data = {}
    data.update(user_info)
    data.update(card_info)
    data.update(repayment_info)
    data.update({"contact_list": contact_info})

    print data

    for k in repayment_field:
        v = data.get(k)
        if v:
            data[k] = int(float(v) * 100)

    for k in exclude_field:
        data.pop(k, None)
    # installment_info, list 类型. import_user_data 不会使用到
    # installment_info = trans_fields(data['installment_info'], inner_field_dic['installment_info'])
    print 'out trans_to_inner_field'
    return data


def trans_fields(data, fields):
    print data
    print fields
    new_data = {v: data[k] for k, v in fields.items() if v and data.get(k)}
    return new_data


def update_attr(instance, update_data, partial=True):
    print 'in update_attr'
    for k, v in update_data.items():
        if partial and not v:
             v = getattr(instance, k)
        setattr(instance, k, v)

    print 'out update_attr'

def get_request_data(request, return_all=False):
    print 'in get_request_data'
    print request
    print request.body
    print request.data
    print request.POST
    print request.data.get('data')
    print '-------'
    # if not request.data.get('data'):
        # msg = u'参数错误: %s' % str(dict(request.data))
        # raise APIException(msg)

    data = request.data.get('data') if request.data.get('data') and not return_all else request.data
    print data
    if len(data) == 1:
        for k,v in data.items():
            if v == '':
                data = json.loads(k)
                data = data.get('data') if data.get('data') and not return_all else data

    print 'out get_request_data'
    return data

M0 = 0
M1 = 30
M2 = 60
M3 = 90
M4 = 120
M5 = 150
def get_collection_type(overdue_days):
    """逾期类型 M1, M2, M3, M3+"""
    data = Apply.COLLECTION_M0
    if overdue_days > M5:
        data = Apply.COLLECTION_M6
    elif overdue_days > M4:
        data = Apply.COLLECTION_M5
    elif overdue_days > M3:
        data = Apply.COLLECTION_M4
    elif overdue_days > M2:
        data = Apply.COLLECTION_M3
    elif overdue_days > M1:
        data = Apply.COLLECTION_M2
    elif overdue_days > M0:
        data = Apply.COLLECTION_M1

    return data


def installment_compare(apply_installment, installment):
    """"""
    print 'in installment_compare'
    print 'apply_installment'
    print apply_installment
    print installment
    is_in_apply = True

    if not apply_installment:
        can_update = True
        is_in_apply = False
        max_overdue_days = installment.overdue_days
        ins_num = installment.installment_number
        return (can_update, is_in_apply, max_overdue_days, ins_num)
    #ains: apply_installment
    ains_should_repay_time = apply_installment.should_repay_time

    should_repay_time = installment.should_repay_time
    overdue_days = installment.overdue_days
    ins_date_start = should_repay_time
    ins_date_end = should_repay_time + timedelta(days=overdue_days)
    print '%s < %s < %s' % (str(ins_date_start), str(ains_should_repay_time), str(ins_date_end))
    if ins_date_start < ains_should_repay_time < ins_date_end:
        can_update = True
        max_overdue_days = installment.overdue_days
        ins_num = installment.installment_number
        return (can_update, is_in_apply, max_overdue_days, ins_num)

    can_update = False
    max_overdue_days = apply_installment.overdue_days
    ins_num = apply_installment.installment_number
    print 'out installment_compare'
    return (can_update, is_in_apply, max_overdue_days, ins_num)


def get_rest_repay_money(apply):
    """apply 对应的应还款金额.

    还款完成时, 返回的是 实际还款金额
    """
    print "in rest_repay_money"
    repayment = apply.repayment
    all_ins = InstallmentDetailInfo.objects.filter(repayment=repayment)
    rest_repay_money = sum([ins.should_repay_amount for ins in all_ins if ins.repay_status == 2]) / 100.0
    if not InstallmentDetailInfo.objects.filter(repayment=repayment, repay_status=2):
        if InstallmentDetailInfo.objects.filter(repayment=repayment, repay_status__in=[3, 8, 9, 10]):
            print "real_repay_amount"
            rest_repay_money = sum([ins.real_repay_amount for ins in all_ins]) / 100.0

    print "out rest_repay_money"
    return rest_repay_money


def apply_trans_duration(apply, ignore_status=False):
    """apply 状态转换之间的耗时"""
    print "in apply_trans_duration"
    if not ignore_status and apply.status not in [Apply.COLLECTION, Apply.COLLECTION_SUCCESS, Apply.REPAY_SUCCESS, Apply.PARTIAL_SUCCESS]:
        return 0

    latest_update_time = apply.update_at or apply.create_at
    now = datetime.now()
    duration = now - latest_update_time
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

def get_org_account(platform_name):
    platform = Platform.objects.get(name = platform_name)
    return platform.org_account

def report_data_collection_money(apply, status_name="", rest_repay_money=0, recover_date=0):
    print "in report_data_collection_money"
    print '-------------------------------'
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
            's1': u"待分配",
            'i': u"未受理",
            's2': u"未受理",
            'ci': u"已受理",
            's3': u"已受理",
            'd': u"部分回款",
            '8': u"已完成",
            '9': u"已完成",
            's4': u"已完成",
            '10': u"续期",
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
        # instalment_number = apply_installment_number(apply)
        try:
            instalment_number = apply.money + 1
        except Exception as e:
            print e
            instalment_number = 0

        money = rest_repay_money or get_rest_repay_money(apply)
        ignore_status = False
        if status_name==u"已流转":
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
        collector_id = ""
        if apply.employee:
            collector_id = apply.employee.user.username
        org_account = get_org_account(apply.platform)
        tags = dict(
            org_account=org_account,
            status=status_name,
            collector_id=collector_id,
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
        response = data_report_client.report_data(json.dumps(data,ensure_ascii=False).encode('utf-8'))
        print "report bi server response:"
        print response
        print "out report_data_collection_money"
        print
        return data
    except Exception as e:
        print "report_data_collection_money error:"
        print e
        print




def update_apply(repayment, installment, platform, repay_status_cn=None, real_repay_money=0, recover_date=None):
    """"""

    print 'update_apply'
    # collection_apply = Apply.objects.filter(Q(repayment = repayment) & Q(type__in=["a", "b", "c", "d", "e", 'g', 'h']) & Q(status__in=['0', 'i', 'ci', 'd', 'k', 't', 'd', 'o', 's1', 's2', 's3'])).order_by('-id')
    collection_apply = Apply.objects.filter(Q(repayment = repayment) & Q(type__in=["a", "b", "c", "d", "e", 'g', 'h'])).order_by('-id')
    money = collection_apply.first().money + 1 if collection_apply.first() else -10
    print repayment
    print collection_apply.first()
    print money
    apply_installment = InstallmentDetailInfo.objects.filter(installment_number=money, repayment=repayment).first()
    rest_repay_money = 0
    can_update, is_in_apply, max_overdue_days, ins_num = installment_compare(apply_installment, installment)
    print '----------\n\n'
    print can_update, max_overdue_days, ins_num

    collection_type = get_collection_type(max_overdue_days)

    print 'collection_apply'
    print collection_apply
    print installment
    print installment.repay_status
    # overdue_days, money 每次都更新
    if collection_apply:
        # 取最近一期的 apply
        collection_apply = collection_apply.filter(money=money-1)
        collection_apply.update(overdue_days=max_overdue_days, money=ins_num-1)
        print 'installment repay_status: %s' % installment.repay_status
        print '-0-' * 100
        if installment.repay_status in [3, 8, 9]:
            repay_status = Apply.PARTIAL_SUCCESS
            if not InstallmentDetailInfo.objects.filter(repayment=repayment, repay_status__in=[1, 2]):
                repay_status = Apply.COLLECTION_SUCCESS
        # 续期
        # elif installment.repay_status in [10] and not InstallmentDetailInfo.objects.filter(repayment=repayment, repay_status__in=[1, 2]):
        elif repayment.repay_status in [10]:
            repay_status = Apply.RENEW
        elif real_repay_money > 0 :
            repay_status = Apply.PARTIAL_SUCCESS
        else:
            repay_status = Apply.WAIT

        collection_apply.update(status=repay_status)

        apply_installmens = InstallmentDetailInfo.objects.filter(repayment=collection_apply.first().repayment, installment_number__gte=collection_apply.first().money + 1)
        if apply_installmens:
            rest_repay_money = sum([
                (ai.real_time_should_repay_amount or ai.should_repay_amount + ai.repay_overdue) - ai.reduction_amount - ai.real_repay_amount
                for ai in apply_installmens])
            repayment_real_repay_amount = sum([ai.real_repay_amount for ai in apply_installmens])
            if repay_status in [Apply.COLLECTION_SUCCESS, Apply.REPAY_SUCCESS]:
                rest_repay_money = repayment_real_repay_amount
            collection_apply.update(rest_repay_money=rest_repay_money, real_repay_money=repayment_real_repay_amount)

        if repay_status_cn in [u'续期', u'扣款成功', u'全额还清', u'减免还清', u'部分还款']:
            print u'回款上报'
            report_data_collection_money(collection_apply.first(), rest_repay_money=real_repay_money, recover_date=recover_date)

    if not can_update:
        return collection_apply.first()

    # if collection_apply.first() and collection_apply.first().status not in [Apply.REPAY_SUCCESS, Apply.COLLECTION_SUCCESS, Apply.RENEW]:
    if collection_apply.first() and collection_apply.first().status not in [Apply.REPAY_SUCCESS, Apply.COLLECTION_SUCCESS]:

        if collection_type > collection_apply.first().type:
            # 类型(m1, m2, ...)的变化
            status = Apply.WAIT
            print "new status"
            print status
            print type(status)
            create_at = datetime.now()

            # collection_apply.update(type=collection_type, money=ins_num - 1, status=status)
            report_data_collection_money(collection_apply.first(), u"已流转")

            collection_apply.update(type=collection_type, money=ins_num - 1, status=status, create_at=create_at, update_at=create_at, overdue_days=max_overdue_days, rest_repay_money=rest_repay_money, ori_collection_amount=rest_repay_money)

            report_data_collection_money(collection_apply.first())
            print '\n\ncccccccccccccc'
            print collection_apply
            print collection_apply.values()
            print 'aaaaaaaaaaaaaaaa\n\n'
        # else:
            # collection_apply.update(type=collection_type, money=i - 1)

        return collection_apply.first()
    else:
        if is_in_apply:
            print 'is in apply'
            return collection_apply.first()

        print "new apply"
        apply_status_dic = {
            3: '9',
            9: '9',
            8: '8',
        }
        status = '0'

        status = apply_status_dic.get(installment.repay_status, '0')
        # 部分还款
        if real_repay_money > 0 and status not in ['8', '9']:
            status = Apply.PARTIAL_SUCCESS

        rest_repay_money = installment.should_repay_amount or 0
        real_repay_amount = installment.real_repay_amount or 0
        collection_apply = Apply(
            create_by=repayment.user, money=ins_num -1, repayment=repayment, status=status, type=collection_type,
            update_at=datetime.now(), create_at=datetime.now(), overdue_days=max_overdue_days,
            rest_repay_money=rest_repay_money, real_repay_money=real_repay_amount, platform=platform,
            ori_collection_amount=rest_repay_money)
        collection_apply.save()



        report_data_collection_money(collection_apply)

        print '\n\ncccccccccccccc'
        print collection_apply
        print 'aaaaaaaaaaaaaaaa\n\n'

        appoint_repayment_record(collection_apply, repayment, installment, platform)
        return collection_apply



def repayment_create_or_update(data, platform, parse_record_id):
    print 'in repayment_create_or_update'
    errors = []
    repayment_data = {}

    try:
        verify_repay_data(data)

        repayment_data = trans_to_repayment(data, platform)
        # 有 订单号, 依据 订单号 + 渠道
        # 没有 订单号, 依据 身份证 + 渠道
        if repayment_data.get('order_number'):
            q = dict(
                order_number=repayment_data['order_number'],
                user__channel=data.get('string_channel'),
                # capital_channel_id=repayment_data['capital_channel_id'],
            )
        else:
            q = dict(
                user__id_no=data['string_idcard_no'],
                user__channel=data.get('string_channel'),
                # capital_channel_id=repayment_data['capital_channel_id'],
            )

        repayment = RepaymentInfo.objects.filter(**q).first()
        print repayment

        # repayment_data['strategy_id'] = yjj_strategy(data['int32_installment_days'], repayment=repayment).strategy_id
        if repayment:
            update_attr(repayment, repayment_data)
        else:
            repayment_data['rest_amount'] = repayment_data['apply_amount']
            repayment = RepaymentInfo(**repayment_data)

        repayment.save()
        print '-------'
        print repayment_data
        print repayment

        repayment_data = dict(id=repayment.id)

        installment_data = installment_create_or_update(data, repayment)
        errors.extend(installment_data['msg'])


        installment = InstallmentDetailInfo.objects.filter(id=installment_data['data']['id']).first()
        update_repayment_status(repayment)
        repay_status = data.get('string_repay_status')
        # 回款时, 添加催记.
        print data
        real_repay_amount = data.get('int32_real_repay_amount', 0)
        recover_date = arrow.get(data.get('string_real_repay_time')).naive
        apply = update_apply(repayment, installment, platform, repay_status, real_repay_amount, recover_date)

        if real_repay_amount:
            parse_record = ParseFileRecord.objects.filter(id=parse_record_id).first()
            create_by = parse_record.creator
            import_repay_collection_record(apply, create_by, real_repay_amount, apply.get_status_display())

    except Exception as e:
        print e
        errors.append(str(e))


    code = 0
    print errors
    if errors:
        code = 1
    data = dict(
        data=repayment_data,
        code=code,
        msg=errors,
    )

    print data
    return data

def import_repay_collection_record(apply, create_by, amount, repay_status=None, bank_card=None):
    """回款记录: 通过数据导入方式
    1. 是否为重复回款数据. 通过 回款记录 来判断.
    2. 添加 催记
    """
    """
    回款数据导入时, 添加 催记.
    {
        "record_type": "扣款",
        "collection_note": "催记内容",
        "create_by": "数据导入用户创建的",
        "apply": "订单",
        # 通过一个函数获得.
        "installment_numbers", ...
    }
    """
    print 'in import_repay_collection_record'
    print locals()
    repay_status = repay_status or apply.get_status_display() or u'扣款成功'
    card_number = bank_card.card_number if bank_card else u'为空'
    collection_note = u'文件导入: 试图扣款%0.2f %s 卡号:%s 金额:%0.2f' % (amount / 100.0, repay_status, card_number, amount/100.0)

    data = dict(
        record_type=CollectionRecord.REPAY,
        collection_note=collection_note,
        create_by=create_by,
        apply=apply,
    )
    extra_data = collection_extra_data(apply)

    data.update(extra_data)

    print data
    add_collection_record(data)

    print 'out import_repay_collection_record'
    return


def update_repayment_status(repayment):
    print 'in update_repayment_status'
    status = 7
    q = {
        'repayment': repayment,
        'repay_status__in': [1, 2, 3, 8, 9],
    }
    installments = InstallmentDetailInfo.objects.filter(**q)
    ins_status = [ins.repay_status for ins in installments]
    if not installments:
        return status

    repaying_status = [s for s in ins_status if s == 1]
    overdue_status = [s for s in ins_status if s == 2]
    # status = '3'
    if repaying_status:
        status = 1
    if overdue_status:
        status = 2

    if not (repaying_status or overdue_status):
        latest_repay_ins = installments.order_by('-should_repay_time').first()
        if latest_repay_ins.repay_status == 8:
            status = 8

        if latest_repay_ins.repay_status == 3:
            status = 3

        if latest_repay_ins.repay_status == 9:
            status = 9

    repayment.repay_status = status
    repayment.save()
    print 'out update_repayment_status'
    return status


def trans_to_repayment(data, platform):
    print 'in trans_to_repayment'
    # 'order_number, amount'
    required_fields = ['amount', 'installment_count']
    int_fields = ['apply_amount', 'installment_count']

    id_card_number = None
    apply_amount = None

    # 回款时, 只需要少量的字段, 其他的字段从 db 中直接取
    if data.get('string_order_number'):
        q = dict(
            order_number=data.get('string_order_number'),
            user__channel=data.get('string_channel'),
            # capital_channel_id=repayment_data['capital_channel_id'],
        )
        print q
        repayment = RepaymentInfo.objects.filter(**q).first()
        print repayment
        if repayment:
            # channel = aa
            id_card_number = repayment.user.id_no
            apply_amount = repayment.apply_amount


    print id_card_number
    print apply_amount
    channel = data.get('string_channel')
    id_card_number = id_card_number or data['string_idcard_no']
    bank_card_number = data.get('string_bank_card_id')

    user = User.objects.filter(id_no=id_card_number.strip(), channel=channel.strip(), platform=platform).first()
    if not user:
        msg = 'user not exist. id_no: %s, channel: %s' % (id_card_number, channel)
        raise ValueError(msg)

    bank_card = BankCard.objects.filter(card_number=bank_card_number).first()
    if not bank_card:
        pass


    inner_field_dic = {
        'string_repay_status': 'repay_status',
        'string_order_number': 'order_number',
        'int32_amount': 'apply_amount',
        # 'int32_amount': 'exact_amount',
        # 'int32_amount': 'repay_amount',
        # 'int32_amount': 'rest_amount',
        'int32_installment_count': 'installment_count',
        'string_repay_status': 'repay_status',
        'string_renew_repay_time': 'renew_repay_time',
        # 'int32_installment_days': 'installment_days',

        # '': 'strategy_id',
        # '': 'bank_card',
        # '': 'user',
        # '': 'reason',

        # '': 'apply_time',
        # 'string_should_repay_time': 'first_repay_day',
        # 'int32_overdue_days': 'overdue_days',

    }
    print data
    new_data = {inner_field_dic[k]: v for k, v in data.items() if v not in ['', None] and k in inner_field_dic}
    print new_data
    if not new_data.get('order_number'):
        new_data['order_number'] = ''
    # if not new_data['capital_channel_id']:
        # new_data['order_number'] = ''
    for k, v in new_data.items():
        if k in int_fields:
            new_data[k] = int(v)

    new_data['user'] = user
    new_data['bank_card'] = bank_card
    new_data['reason'] = ""

    # new_data['strategy_id'] = Strategy2.objects.filter(name='import').first().strategy_id
    if new_data.get('repay_status') in [u'续期', '续期']:
        renew_repay_time = new_data.pop('renew_repay_time', None)
        if renew_repay_time:
            # should_repay_time = renew_repay_time
            # new_data['should_repay_time'] = should_repay_time
            new_data['repay_status'] = 10
        else:
            msg = 'error: renew repayment must have renew_repay_time. %s' % renew_repay_time
            raise ValueError(msg)
    else:
        new_data['repay_status'] = 2

    new_data['exact_amount'] = apply_amount or new_data['apply_amount']
    new_data['repay_amount'] = apply_amount or new_data['apply_amount']
    new_data['platform'] = platform
    # new_data['product'] = product
    # new_data['repay_status'] = new_data['rest_amount']

    print new_data
    print 'out trans_to_repayment'
    return new_data



def required_field_validate(fields, required_fields):
    """是否包含了所有 必填字段"""
    exclude_fields = set(required_fields) - set(fields)
    is_valid = not exclude_fields

    return is_valid


def yjj_strategy(installment_days, installment_count=1, repayment=None):
    """依据 贷款天数, 贷款期数 来获取 策略

    当前只有 7 天 和 14 天
    """
    print 'in yjj_strategy'
    print locals()
    if repayment and not installment_days:
        strategy = repayment.strategy
    else:
        q = {
            'name': u'易借金 %s天' % installment_days
        }
        strategy = Strategy2.objects.filter(**q).first()

        if not strategy:
            strategy = Strategy2.objects.filter().first()

    print 'out yjj_strategy'
    return strategy


def yjj_overdue(overdue_days, repay_status, installment, reduction_amount=0, channel=None):
    print "in yjj_overdue"
    print locals()
    RENEW_FEE = 20 * 100
    PENALTY_ONE_DAY = 20 * 100
    PENALTY_CEIL = 1800 * 100
    if channel in ['易借金', '人人催', u'易借金', u'人人催']:
        PENALTY_CEIL = 900 * 100
    overdue_days = max(0, overdue_days)
    repay_penalty = overdue_days * PENALTY_ONE_DAY
    repay_penalty = min(repay_penalty, PENALTY_CEIL)
    if repay_status in [10, u'续期']:
        amount = installment.repay_interest + repay_penalty + RENEW_FEE
    elif repay_status in [u'减免还清']:
        amount = installment.repayment.apply_amount + installment.repay_interest + repay_penalty - reduction_amount
    else:
        # amount = installment.should_repay_amount + repay_penalty
        amount = installment.repayment.apply_amount + installment.repay_interest + repay_penalty

    # amount *= 100
    print locals()
    print "out yjj_overdue"
    return amount


def yjj_interest(days, channel=None, amount=0):
    print 'in interest'
    interest = 100
    if channel in ['蓝领贷', u'蓝领贷']:
        if amount in [180000]:
            interest = 200
        interest *= 100
        return interest

    if channel in ['蚂蚁快线', u'蚂蚁快线']:
        interest *= 100
        return interest

    if not days:
        return 0

    days = int(days)

    interest_dic = {
        7: 50,
        14: 100,
    }

    interest = interest_dic.get(days, 0)
    interest *= 100

    return interest


def verify_repay_data(data):
    """验证 yjj 还款数据正确性"""

    print 'in verify_repay_data'
    should_repay_time = data.get('string_should_repay_time')
    if not should_repay_time:
        msg = u'should repay time in null'
        raise ValueError(msg)
    repay_status = data.get('string_repay_status')
    real_repay_time = data.get('string_real_repay_time')
    real_repay_amount = data.get('int32_real_repay_amount')
    # installment_days = data.get('int32_installment_days')
    order_number = data.get('string_order_number')
    reduction_amount = data.get('int32_reduction_amount', 0)
    channel = data.get('string_channel')
    print locals()

    # 回款数据 正确性判断
    if not real_repay_amount:
        return

    valid_repay_status = [u'续期', u'扣款成功', u'全额还清', u'减免还清', u'部分还款']
    if repay_status not in valid_repay_status:
        msg = u'repay status error'
        # msg = u'还款状态 错误: %s 不在 %s 中' % (repay_status, ",".join(valid_repay_status))
        # msg = u'应还金额错误: 系统计算金额 != 文件导入金额, %s != %s' % (amount, real_repay_amount)
        raise ValueError(msg)

    # 部分还款: 不验证还款金额
    if repay_status in [u'部分还款']:
        return

    overdue_days = (arrow.get(real_repay_time) - arrow.get(should_repay_time)).days
    if channel in ['易借金', '人人催', u'易借金', u'人人催']:
        overdue_days -= 1
    # interest = yjj_interest(installment_days)
    repayment = RepaymentInfo.objects.filter(order_number=order_number).first()
    if not repayment:
        print 'no repayment '
        id_no = data.get('string_idcard_no')
        repayment = RepaymentInfo.objects.filter(user__id_no=id_no, user__channel=channel).first()
        data['string_order_number'] = repayment.order_number
    installment = InstallmentDetailInfo.objects.filter(repayment=repayment).first()
    print locals()
    amount = yjj_overdue(overdue_days, repay_status, installment, reduction_amount, channel)
    if amount != real_repay_amount:
        msg = u'should repay amount error: calc_amount != file_amount, %s != %s' % (amount, real_repay_amount)
        # msg = u'应还金额错误: 系统计算金额 != 文件导入金额, %s != %s' % (amount, real_repay_amount)
        raise ValueError(msg)
    # renew_repay_time = data.get('string_renew_repay_time')

    print 'out verify_repay_data'
    return


def installment_record_create_or_update(installment, update_data, partial=True):
    print 'in installment_record_create_or_update'
    print update_data
    update_data.pop('repayment', None)
    if partial:
        update_data = {k: v for k, v in update_data.items() if v}

    renew_time = update_data['renew_time']
    q = {
        'id': installment.id,
        'renew_time': renew_time,
    }
    installment_data = InstallmentDetailInfo.objects.filter(id=installment.id).values()
    if installment_data:
        data = installment_data[0]
        data.update(update_data)
        print data
        data.pop('id', None)

        installment_record = InstallmentRecord.objects.filter(**q).first()
        if not installment_record:
            installment_record = InstallmentRecord(**data)
            installment_record.save()

        print 'out installment_record_create_or_update'
        return installment_record


def installment_reset(installment, should_repay_time, repay_interest, real_time_should_repay_amount, update_at):
    """分期 信息重置.续期时, 会用到"""

    # repay_interest = yjj_interest(data.get('int32_installment_days'))
    print 'in installment_reset'
    update_data = dict(
        should_repay_time=should_repay_time,
        repay_interest=repay_interest,
        should_repay_amount=real_time_should_repay_amount,
        real_time_should_repay_amount=real_time_should_repay_amount,
        update_at=update_at,
    )

    reset_data = dict(
        real_repay_time=None,
        real_repay_amount=0,
        reduction_amount=0,
        repay_status=7,
        repay_overdue=0,
        repay_principle=0,
        repay_overdue_interest=0,
        repay_penalty=0,
        repay_bank_fee=0,
        repay_fee=0,
        overdue_days=0,
        repay_channel_description=''
    )
    data = {}
    data.update(reset_data)
    data.update(update_data)

    print data
    update_attr(installment, data, partial=False)
    installment.save()

    print 'out installment_reset'
    return installment


def trans_to_installment(data, repayment):
    print 'in trans_to_installment'
    print data
    print repayment
    required_fields = ['installment_number', 'should_repay_time', 'real_time_should_repay_amount']
    # repay_status_dic = {
        # u'催收完成':
        # u'扣款成功':

    # }
    inner_field_dic = {
        # 'repayment': '',
        'int32_installment_number': 'installment_number',
        'string_should_repay_time': 'should_repay_time',
        'string_renew_repay_time': 'renew_repay_time',
        'string_real_repay_time': 'real_repay_time',
        'int32_real_repay_amount': 'real_repay_amount',
        'int32_should_repay_amount': 'should_repay_amount',
        'int32_real_time_should_repay_amount': 'real_time_should_repay_amount',
        'int32_reduction_amount': 'reduction_amount',
        # '': 'ori_should_repay_amount',
        'int32_overdue_interest': 'repay_overdue_interest',
        'int32_penalty': 'repay_penalty',
        'int32_overdue_days': 'overdue_days',
        'string_repay_status': 'repay_status',
        'string_repay_channel': 'repay_channel_description',
        # 'string_installment_days': 'repay_channel_description',

        # '': 'update_at',
        # '': 'order_number',
    }
    new_data = {inner_field_dic[k]: v for k, v in data.items() if v not in ['', None] and k in inner_field_dic}
    print data.keys()
    print inner_field_dic.keys()
    print new_data
    new_data['overdue_days'] = int(new_data.get('overdue_days', 0))
    # new_data['installment_days'] = int(new_data.get('installment_days', 1))
    new_data['installment_number'] = int(new_data.get('installment_number', 0))
    new_data['repay_overdue'] = new_data.get('repay_overdue_interest', 0) + new_data.get('repay_penalty', 0)

    overdue_days = new_data.get('overdue_days', 0)
    repay_status = 7

    if overdue_days == 0:
        should_repay_time = datetime.strptime(new_data['should_repay_time'], '%Y-%m-%d')
        now = datetime.now()
        overdue_days = (now - should_repay_time).days

    if overdue_days > 0:
        repay_status = RepaymentInfo.OVERDUE
    elif overdue_days == 0:
        repay_status = RepaymentInfo.REPAYING

    real_repay_amount = new_data.get('real_repay_amount', 0)
    if new_data.get('repay_status') in [u'扣款失败']:
        real_repay_amount = 0
        new_data['real_repay_amount'] = real_repay_amount

    elif new_data.get('repay_status') in [u'续期']:
        renew_repay_time = new_data.pop('renew_repay_time', None)
        if renew_repay_time:
            # should_repay_time = renew_repay_time
            new_data['should_repay_time'] = renew_repay_time
            repay_status = 10

    is_done = False

    installment = InstallmentDetailInfo.objects.filter(repayment=repayment).first()
    real_time_should_repay_amount = new_data.get('real_time_should_repay_amount')

    if not real_time_should_repay_amount and installment:
        real_time_should_repay_amount = installment.real_time_should_repay_amount

    if new_data.get('repay_status') in [u'续期']:
        # real_time_should_repay_amount += RENEW_FEE
        should_repay_time = data.get('string_should_repay_time')
        real_repay_time = data.get('string_real_repay_time')
        overdue_days = (arrow.get(real_repay_time) - arrow.get(should_repay_time)).days
        overdue_days -= 1
        real_time_should_repay_amount = yjj_overdue(overdue_days, '', installment) + RENEW_FEE
        new_data['real_time_should_repay_amount'] = real_time_should_repay_amount

    if installment:
        new_data['should_repay_amount'] = installment.should_repay_amount

    if real_time_should_repay_amount and not new_data.get('should_repay_amount', 0):
        if not (installment and installment.should_repay_amount):
            new_data['should_repay_amount'] = real_time_should_repay_amount



    if real_repay_amount:
        # is_done = real_repay_amount == new_data.get('repay_penalty', 0) + new_data.get('should_repay_amount', 0) + new_data.get('repay_overdue_interest', 0)
        is_done = real_repay_amount == new_data.get('real_time_should_repay_amount', 0)
        if not new_data.get('real_repay_time'):
            new_data['real_repay_time'] = datetime.now()

    print new_data
    if new_data.get('repay_status') in [u'催收完成', u'扣款成功', u'全额还清', u'减免还清'] or is_done:
        repay_status = RepaymentInfo.DONE
        if repay_status == RepaymentInfo.OVERDUE:
            repay_status = RepaymentInfo.OVERDUE_DONE

    new_data['repay_status'] = repay_status
    repay_interest = yjj_interest(data.get('int32_installment_days', 0), data.get('string_channel'), data.get('int32_amount'))
    if repay_interest:
        new_data['repay_interest'] = repay_interest

    repay_channel_description = new_data.get('repay_channel_description')
    if repay_channel_description:
        repay_channel_dic = {k: v for v, k in InstallmentDetailInfo.repay_channel_type_t}
        print repay_channel_description
        print repay_channel_dic
        new_data['repay_channel'] = repay_channel_dic.get(repay_channel_description, 5)

    print overdue_days
    print new_data
    print 'out trans_to_installment'
    return new_data


def installment_create_or_update(data, repayment):
    print 'in installment_create_or_update'
    errors = []
    installment_data = {}
    try:
        installment_data = trans_to_installment(data, repayment)
        installment_data['repayment'] = repayment
        installment = InstallmentDetailInfo.objects.filter(repayment=repayment, installment_number=installment_data.get('installment_number', 0)).first()

        strategy_id = yjj_strategy(data.get('int32_installment_days', 1), repayment=repayment).strategy_id
        print locals()
        if installment:

            # 续期,创建一条 分期记录, 并将 分期 数据进行重置
            if installment_data['repay_status'] == 10:
                should_repay_time = installment_data.pop('should_repay_time')
                repay_interest = installment_data.pop('repay_interest')
                real_time_should_repay_amount = 0
                update_at = datetime.now()
                real_time_should_repay_amount = repayment.apply_amount + repay_interest

                installment_data['strategy_id'] = installment.repayment.strategy.strategy_id
                installment_data['renew_time'] = should_repay_time
                installment_record_create_or_update(installment, installment_data)
                installment_reset(installment, should_repay_time, repay_interest, real_time_should_repay_amount, update_at)
            else:
                installment_data['update_at'] = datetime.now()
                update_attr(installment, installment_data)
                installment.save()
        else:
            installment_data['ori_should_repay_amount'] = installment_data['should_repay_amount']
            installment = InstallmentDetailInfo(**installment_data)
            installment.save()

        # 续期时, 期款记录 需要存储 策略. 所以在这里 更新 贷款策略.
        repayment.strategy_id = strategy_id
        repayment.save()

        installment_data = dict(id=installment.id)
    except Exception as e:
        errors.append(str(e))

    code = 0
    if errors:
        code = 1

    data = dict(
        data=installment_data,
        code=code,
        msg=errors,
    )

    print data
    print 'out installment_create_or_update'
    return data



def get_import_module_detail(pk):
    print 'in get_import_module_detail'
    import_module = ImportModule.objects.filter(id=pk, status__gte=0).first()
    serializer = ImportModuleSerializer(import_module)

    print serializer.data
    return serializer.data


def cute_exception_handler(exc, context):
    """出错时, 返回 code, msg, data
    前端要求, http status 返回 200

    除了返回数据, 其他逻辑和 exception_handler 相同
    """
    print 'in cute_exception_handler'

    def get_exc_message(messages):
        if not messages:
            return ''

        if isinstance(messages, list):
            return " ".join(messages[0])

        if isinstance(messages, dict):
            print messages.values()
            return " ".join(messages.values()[0])

    if isinstance(exc, exceptions.APIException):
        headers = {}
        if getattr(exc, 'auth_header', None):
            headers['WWW-Authenticate'] = exc.auth_header
        if getattr(exc, 'wait', None):
            headers['Retry-After'] = '%d' % exc.wait

        if isinstance(exc.detail, (list, dict)):
             data = dict(
                code=500,
                msg=get_exc_message(exc.detail),
                data={}
            )
        else:
            data = dict(
                code=500,
                msg=exc.detail,
                data={}
            )


        set_rollback()
        # return Response(data, status=exc.status_code, headers=headers)
        return Response(data, headers=headers)

    elif isinstance(exc, Http404):
        msg = _('Not found.')
        data = dict(
            code=404,
            msg=six.text_type(msg),
            data={}
        )

        set_rollback()
        # return Response(data, status=status.HTTP_404_NOT_FOUND)
        return Response(data)

    elif isinstance(exc, PermissionDenied):
        msg = _('Permission denied.')
        data = dict(
            code=403,
            msg=six.text_type(msg),
            data={}
        )

        set_rollback()
        # return Response(data, status=status.HTTP_403_FORBIDDEN)
        return Response(data)

    # Note: Unhandled exceptions will raise a 500 error.
    return None



def import_field_inner(queryset):
    """数据导入: 预置字段"""
    print 'in retrieve inner field'
    print queryset
    print settings
    print settings.IMPORT_DATA['module_name']
    instance = queryset.filter(show_name=settings.IMPORT_DATA['module_name']).first()
    print instance
    if not instance:
        return {}

    fields_str = instance.required_fields
    fields = json.loads(fields_str)
    fields = {f['field_id']: f for f in fields}
    # ids = [f['field_id'] for f in fields]
    ids = fields.keys()
    print fields
    print ids
    inner_fields = ProfileField.objects.filter(id__in=ids)

    inner_data = inner_fields.values('id', 'name', 'show_name')

    for d in inner_data:
        fid = d['id']
        is_required = bool(fields[fid]['is_must'])
        d['is_required'] =is_required
    inner_data = list(inner_data)
    inner_data.sort(key=lambda d: not d['is_required'])

    return inner_data


class CutePagination(pagination.LimitOffsetPagination):
    """自定义: 返回结果"""

    def get_paginated_response(self, data):
        return Response({
            'code': data['code'],
            'msg': data['msg'],
            'count': data['count'],
            'data': data['data'],
            # 'links': {
                # 'next': self.get_next_link(),
                # 'previous': self.get_previous_link()

                # },
            # 'count': self.page.paginator.count,

            })


class CutePageNumberPagination(pagination.PageNumberPagination):
    """自定义: 返回结果"""
    page_size_query_param = 'page_size'

    def get_paginated_response(self, data):
        return Response({
            'code': data['code'],
            'msg': data['msg'],
            'count': data['count'],
            'data': data['data'],
            # 'links': {
                # 'next': self.get_next_link(),
                # 'previous': self.get_previous_link()

                # },
            # 'count': self.page.paginator.count,

            })





class CuteAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        """
        Enforce CSRF validation for session based authentication.
        """
        return


class CuteViewSet(viewsets.ModelViewSet):
    """自定义: delete

    destroy: 将 status 修改为 负数. 在状态 < 0 时, 数据对用户都是不可见.
    """


    pagination_class = CutePagination
    authentication_classes = (CuteAuthentication, BasicAuthentication)

    serializer_class_retrieve = None
    serializer_class_list = None
    serializer_class_create = None
    csrf_exempt = True
    code = 0
    msg = ''
    platform = None

    def get_queryset(self):
        """queryset 状态 < 0 的不返回"""
        queryset = self.queryset
        if isinstance(queryset, QuerySet):
            # Ensure queryset is re-evaluated on each request.
            queryset = queryset.all()

        if self.platform:
            queryset = queryset.filter(status__gte=0, platform__in = self.platform).order_by('-update_at')

        return queryset

    def is_retrieve(self):
        """通过有没有 lookup_field 判断"""
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        pk = self.kwargs.get(lookup_url_kwarg)

        return True if pk else False

    def get_serializer_class(self):
        """list, retrieve, create, update 使用不同的 serializer

        create: serializer_class_create
        list: serializer_class_list
        retrieve: serializer_class_retrieve
        """

        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        pk = self.kwargs.get(lookup_url_kwarg)
        print self.lookup_url_kwarg
        print self.lookup_field
        print self.kwargs
        print pk
        print '--------'

        is_get = self.request.method == 'GET'
        if not is_get:
            return self.serializer_class_create or self.serializer_class

        if self.is_retrieve():
            return self.serializer_class_retrieve or self.serializer_class
        else:
            return self.serializer_class_list or self.serializer_class
        # print self.serializer_class

        return self.serializer_class


    def retrieve(self, request, *args, **kwargs):
        print get_import_module_detail(1)
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        data = dict(
            code=self.code,
            msg=self.msg,
            data=serializer.data
        )
        return Response(data)


    def list(self, request, *args, **kwargs):
        self.platform = get_employee_platform(request).values_list('name', flat = True)
        queryset = self.filter_queryset(self.get_queryset())

        data = dict(
            code=self.code,
            msg=self.msg,
            count=queryset.count(),
        )
        if not queryset:
            print 'CuteViewSet: queryset is []'
            return Response(data)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            data['data'] = serializer.data

            return self.get_paginated_response(data)
        serializer = self.get_serializer(queryset, many=True)
        data['data'] = serializer.data

        print 'CuteViewSet: out list'
        return Response(data)

    def create(self, request, *args, **kwargs):
        """

        update_data: dict 额外的数据, 需要验证.
        valid_data: dict 额外的数据, 不需要验证.
        """
        print 'CuteViewSet: in create'
        update_data = kwargs.get('update_data', {})
        valid_data = kwargs.get('valid_data', {})

        data = get_request_data(request)
        data.update(update_data)
        amount_ceil = data.get('amount_ceil', 1)
        if isinstance(amount_ceil, (int, long)) and amount_ceil > 2147483647:
            return Response(
                data=dict(
                        code=500,
                        msg=u"请确保贷款金额上限小于或者等于 21474836.47元",
                        data=""
                    )
                )
        print '890 '
        print data
        serializer = self.get_serializer(data=data)
        print serializer
        serializer.is_valid(raise_exception=True)
        # serializer.is_valid()
        serializer.validated_data.update(valid_data)
        print 'data --' * 20
        print serializer.validated_data
        self.perform_create(serializer)
        # print serializer.data
        headers = self.get_success_headers(serializer.data)

        data = dict(
            code=self.code,
            msg=self.msg,
            data=serializer.data,
        )
        print 'CuteViewSet: out create'
        # return Response(data, status=status.HTTP_201_CREATED, headers=headers)
        return Response(data, headers=headers)

    def validate_immutable_instance(self, instance):
        status = instance.status
        if status in [USING]:
            status_msg = '正在使用中'
            msg = u'{}, {} 不能修改或删除.'.format(instance.name, status_msg)
            raise APIException(msg)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        print 'CuteViewSet: in update'
        instance = self.get_object()
        self.validate_immutable_instance(instance)

        data = get_request_data(request)
        serializer = self.get_serializer(instance, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        print '0129' * 10
        print serializer.validated_data
        if not serializer.validated_data.get('update_at'):
            serializer.validated_data['update_at'] = datetime.now()
        print serializer.validated_data
        self.perform_update(serializer)

        data = dict(
            code=self.code,
            msg=self.msg,
            data=serializer.data,
        )

        print 'CuteViewSet: out update'
        return Response(data)

    def destroy(self, request, *args, **kwargs):
        """删除: 将 instance 状态 修改为 -1 (< 0 表示用户不可见)"""
        instance = self.get_object()
        self.perform_destroy(instance)
        # return Response(status=status.HTTP_204_NO_CONTENT,data=0)
        data = dict(
            code=0,
            msg='',
            data={},
        )
        return Response(data=data)

    def perform_destroy(self, instance):
        # instance.delete()
        # instance['status'] = -1
        # instance.save()
        partial = True
        data = dict(
            status=-1,
        )
        serializer = self.get_serializer(instance, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)


def appoint_repayment_record(apply, repayment, installment, platform=None, product=None):
    """进件数据

    多期的逻辑还没实现
    """
    try:
        print "in appoint_repayment_record"

        q = {
            'repayment_id': repayment.id,
            'installment_id': installment.id,
            'apply': apply,
        }

        record = AppointRepaymentRecord.objects.filter(**q)
        if record:
            msg = u'委案数据: 已存在. repayment: %s, installment: %s, apply: %s' % (repayment, installment, apply)
            print msg
            print "out dingdang_repayment_record"

            return 1

        overdue_days = installment.overdue_days
        appoint_data = dict(
            apply=apply,
            # collector = models.ForeignKey(Employee, blank=True, null=True, help_text="催收人员")
            installment_id =installment.id,
            should_repay_amount=installment.real_time_should_repay_amount,
            should_repay_time=installment.should_repay_time,
            overdue_days=overdue_days,
            overdue_type=get_collection_type(overdue_days),
            repayment_id=repayment.id,
            # strategy_id=repayment.strategy.strategy_id,
            apply_amount=repayment.apply_amount,
            platform=platform or repayment.platform,
            product=product or repayment.product,
        )
        print appoint_data

        user = repayment.user
        print user
        user_dic = dict(
            id_no=user.id_no,
            channel=user.channel,
            user_name=user.name,
            phone_no=user.phone_no,
        )

        appoint_data.update(user_dic)
        record = AppointRepaymentRecord(**appoint_data)
        record.save()

        print "out appoint_repayment_record"

    except Exception as e:
        print 'error: '
        print e
        return -1

def parse_contact_data(datas):
    """处理从文件中读取的原始数据

    文件格式:
        姓名, 身份证, 渠道, 联系人号码, 联系人姓名, 联系人关系
        name1, 513021199308121111, 蚂蚁快线, 15775676780, ,
             ,                   ,         , 15775676781, ,
        name2, 130622199112011111, 蚂蚁快线, 18395751290, ,
             ,                   ,         , 18395751291, ,

    [{u'string_contact_relation1': None, u'string_name': u'\u94b1\u9e4f\u98de', u'string_contact_phone1': 15775676780L, u'string_idcard_no': u"'513021199308120195", u'string_contact_name1': None, u'string_channel': u'\u8682\u8681\u5feb\u7ebf'}, {u'string_contact_relation1': None, u'string_name': None, u'string_contact_phone1': 15181890958L, u'string_idcard_no': u"'", u'string_contact_name1': None, u'string_channel': None}, {u'string_contact_relation1': None, u'string_name': None, u'string_contact_phone1': 18481900907L, u'string_idcard_no': u"'", u'string_contact_name1': None, u'string_channel': None}, {u'string_contact_relation1': None, u'string_name': None, u'string_contact_phone1': 18682839623L, u'string_idcard_no': u"'", u'string_contact_name1': None, u'string_channel': None}, {u'string_contact_relation1': None, u'string_name': u'\u5b89\u68a6\u96c4', u'string_contact_phone1': 18395751292L, u'string_idcard_no': u"'130622199112015014", u'string_contact_name1': None, u'string_channel': u'\u8682\u8681\u5feb\u7ebf'}, {u'string_contact_relation1': None, u'string_name': None, u'string_contact_phone1': 18731427991L, u'string_idcard_no': u"'", u'string_contact_name1': None, u'string_channel': None}, {u'string_contact_relation1': None, u'string_name': None, u'string_contact_phone1': 15076945004L, u'string_idcard_no': u"'", u'string_contact_name1': None, u'string_channel': None}, {u'string_contact_relation1': None, u'string_name': None, u'string_contact_phone1': 15832899944L, u'string_idcard_no': u"'", u'string_contact_name1': None, u'string_channel': None}]"'"}"'"}"'"}"'"}"'"}"'"}"'"}"'"}]
    """
    print 'in parse_contact_data'
    print datas
    # user_keys = ['name', 'id_no', 'channel']
    # contact_keys = ['name', 'id_no', 'phone_no', 'relationship', 'relationship_desc']
    user_keys_dic = {
        'string_name': 'name',
        'string_idcard_no': 'id_no',
        'string_channel': 'channel',
    }

    contact_keys_dic = {
        'string_contact_name1': 'name',
        'string_contact_phone1': 'phone_no',
        'string_contact_relation1': 'relationship_desc',
    }
    contact_type_dic = {v: k for k, v in ContactInfo.contact_type_t}

    user_datas = {}
    for data in datas:
        user_data = {user_keys_dic[k]: v for k, v in data.items() if v not in ['', None] and k in user_keys_dic}
        contact_data = {contact_keys_dic[k]: v for k, v in data.items() if v not in ['', None] and k in contact_keys_dic}
        if not contact_data.get('phone_no'):
            msg = u'phone_no dont exist'
            raise KeyError(msg)

        contact_relation = contact_data.get('relationship_desc')
        contact_data['relationship'] = ContactInfo.UNKNOWN
        if contact_relation:
            relationship = contact_type_dic.get(contact_relation, ContactInfo.UNKNOWN)

        # 用户名 为空时, 默认为上一条数据
        if user_data.get('name'):
            key = "%s_%s_%s" % (user_data['name'], user_data['id_no'], user_data['channel'])
            # 默认获取之前的 数据
            user_data = user_datas.get(key, user_data)
        else:
            user_data = latest_user_data
            key = "%s_%s_%s" % (user_data['name'], user_data['id_no'], user_data['channel'])

        user_contact_data = user_data.get('contact')
        if user_contact_data:
            user_contact_data.append(contact_data)
        else:
            user_data['contact'] = [contact_data]

        user_datas[key] = user_data
        latest_user_data = user_data
    print user_datas
    print 'out parse_contact_data'

    return user_datas


def trans_to_contact(datas):
    """转换为 contact 格式"""

    print 'in trans_to_contact'
    contact_datas = []
    for _k, data in datas.items():
        q_user = {
            'name': data['name'],
            'channel': data['channel'],
            'id_no': data['id_no'],
        }
        user = User.objects.filter(**q_user).first()

        contact_data = data['contact']
        _ = [_cd.update(dict(owner=user)) for _cd in contact_data]
        contact_datas.extend(contact_data)

    print contact_datas
    print 'out trans_to_contact'
    return contact_datas


def contact_create_or_update(datas):
    user_contact_datas = parse_contact_data(datas)
    contact_datas = trans_to_contact(user_contact_datas)
    for data in contact_datas:
        contact_info = ContactInfo(**data)
        contact_info.save()

    return True

# def trans_to_contactinfo():
    # """转换为 contactinfo 格式(model)"""
    # pass






