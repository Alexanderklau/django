# -*- coding: utf-8 -*-
"""数据上报功能"""
import json
import time

from datetime import datetime
from redis import StrictRedis
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import requests
from business_manager.review import redis_client
from business_manager.review import data_report_client
from business_manager.python_common.log_client import CommonLog as Log
from business_manager.business_data.business_data_report_client import BusinessDataReportClient as ReportClient
from business_manager.order.apply_models import Apply
from business_manager.collection.models import InstallmentDetailInfo
from business_manager.import_data.services import get_org_account

redis = StrictRedis(host=settings.DATA_REPORT_SERVER['REDIS'], port=settings.DATA_REPORT_SERVER['REDIS_PORT'], 
                   password=settings.DATA_REPORT_SERVER['REDIS_AUTH'], db=settings.DATA_REPORT_SERVER['REDIS_DB'])

report_client = ReportClient(settings.DATA_REPORT_SERVER['HOST'], settings.DATA_REPORT_SERVER['PORT'], redis, Log())


def _report_data(data=None):
    """上报数据"""
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if not data:
        Log().warn('_report_data, data: None, time: {time}'.format(time=now))
        return
    try:
        if isinstance(data, dict):
            data = json.dumps(data, ensure_ascii=False)
        result = report_client.report_data(data)
    except Exception, e:
        result = 'Failed!'
        print 'report_data failed! \n', e
    finally:
        Log().info('_report_data, data: {0}, result: {1}, time: {2}'.format(data, result, now))
    return result

def status_duration(apply, ignore_status=None):
    """催收状态耗时"""
    if apply.status in [Apply.WAIT_DISTRIBUTION, Apply.NOT_ACCEPT, Apply.APPLY_PROCESSING, Apply.COMPLETED]:
        lastest = apply.update_at or apply.create_at
        duration = datetime.now() - lastest
        return int(duration.total_seconds())
    return 0


def iapply_installment_number(apply):
    """返回对应的期数"""
    installments = InstallmentDetailInfo.objects.filter(repayment=apply.repayment, repay_status=2).order_by('id')
    if installments:
        return str(installments[0].installment_number)
    return ''

def get_real_repay_money(apply=None):
    repayment = apply.repayment
    real_repay_money = 0
    all_ins = InstallmentDetailInfo.objects.filter(repayment=repayment, repay_status__in=[3,8,9])
    real_repay_money = sum([ins.real_repay_amount for ins in all_ins]) / 100.0
    return real_repay_money
    

def get_rest_repay_money(apply=None):
    repayment = apply.repayment
    all_ins = InstallmentDetailInfo.objects.filter(repayment=repayment)
    rest_repay_money = sum([ins.should_repay_amount for ins in all_ins if ins.repay_status == 2]) / 100.0
    if not InstallmentDetailInfo.objects.filter(repayment=repayment, repay_status=2):
        if InstallmentDetailInfo.objects.filter(repayment=repayment, repay_status__in=[3, 8]):
            rest_repay_money = sum([ins.real_repay_amount for ins in all_ins]) / 100.0

    return rest_repay_money


def apply_installment_number(apply):
    """"""
    day_and_numbers = [
        (150, 6),
        (120, 5),
        (90, 4),
        (60, 3),
        (30, 2),
    ]
    overdue_days = apply.overdue_days
    installment_count = 1
    installments_numbers = []
    for dn in day_and_numbers:
        day, number = dn
        if overdue_days >= day:
            installment_count = number
            break
    
    installments = InstallmentDetailInfo.objects.filter(repayment=apply.repayment, repay_status__in=[2, 3, 8, 9]).order_by("-id")
    overdue_installment_count = installments.count()

    overdue_installments = InstallmentDetailInfo.objects.filter(repayment=apply.repayment, repay_status__in=[2]).order_by("id")
    min_overdue_installment_number = 0
    if overdue_installments.first():
        min_overdue_installment_number = overdue_installments.first().installment_number
    installment_number = installments.first().installment_number
    installments_numbers = range(installment_number - installment_count + 1, installment_number + 1)
    return max(installment_number - installment_count, min_overdue_installment_number, 0)


def report_collection(apply=None, status_name="", rest_repay_money=0, recover_date=0):
    """催收上报"""
    
    applies_type = {
        'a': 'all',
        'b': 'm1',
        'c': 'm2',
        'd': 'm3',
        'e': 'm4',
        'g': 'm5',
        'h': 'm5+'
    }

    applies_status = {
        's1': u'待分配',
        's2': u'未受理',
        's3': u'已受理',
        's4': u'已完成',
        's5': u'部分回款',
        's7': u'已流转',
        's8': u'催记',
        's9': u'失效'
    }
    print 'apply:', apply
    fields = {
        "apply_id": apply.id,
        "money": rest_repay_money or get_real_repay_money(apply),
        "spend_time": status_duration(apply),
        "assign_date": int(time.mktime(apply.create_at.timetuple()))
    }

    if recover_date:
        recover_date = int(time.mktime(recover_date.timetuple()))
    elif apply.status in ['s4', '8', '9', 'd']:
        recover_date = int(time.time())
    fields.update({
        "recover_date": recover_date
    })
    
    if apply.status in ['s1', '0']:
        _status_name = applies_status.get('s1')
    elif apply.status in ['s2', 'i']:
        _status_name = applies_status.get('s2')
    elif apply.status in ['s3', 'ci']:
        _status_name = applies_status.get('s3')
    elif apply.status in ['s4', '8', '9']:
        _status_name = applies_status.get('s4')
    elif apply.status in ['d', ]:
        _status_name = applies_status.get('s5')
    else:
        _status_name = apply.get_status_display()

    org_account = get_org_account(apply.platform)
    tags = {
        'org_account': org_account,
        'status': status_name if status_name else _status_name,
        'collector_id': apply.employee.user.username if apply.employee else '',
        'collection_type': applies_type.get(apply.type),
        'instalment_number': int(apply.money) + 1
    }
    
    data = {
        'measurement': 'collection_money',
        'time': int(time.time() * pow(10, 9)),
        'tags': tags,
        'fields': fields
    }
    print '-' * 32
    try:
        # print _report_data(data)
        print data
        result = data_report_client.report_data(json.dumps(data))
        print 'collection report : ', result 
    except Exception, e:
        print 'report data {} failed!'.format(data)
        print e
            

def _report_call_data(phone_num=None, in_out=None, request=None, redis_apply_id=None):
    """呼叫日期"""
    r = requests.get()


@require_http_methods(['POST'])
@csrf_exempt
def report_call_action(request):
    """"""
    data = {
        "measurement": "call_report",
        "time": int(time.time() * pow(10, 9)),
    }
    Log().info('in report_call_action')
    print '-' * 64, data 
    print request.POST
    Log().info(request.POST)

    order = Apply.objects.filter(pk=request.POST.get('apply_id')).first()
    print order
    org_account = get_org_account(order.platform)
    tags = {
        "org_account": org_account,
        "collector_id": order.employee.user.username if order.employee else '',
        "is_connected": request.POST.get('is_connected'),
        "call_type": request.POST.get('call_type'),
        "collection_type": request.POST.get('collection_type')
    }
    print 'tags:', tags
    fields = {
        "apply_id": request.POST.get('apply_id'),
        "call_duration": int(request.POST.get('call_duration', 0)),
        "wait_time": int(request.POST.get('wait_time', 0)),
        "phone_number": request.POST.get('phone_number', '')
    }
    print 'fields:', fields
    data.update({
        "tags": tags,
        "fields": fields
    })
    try:
        #result = _report_data(data)
        Log().info(data)
        result = data_report_client.report_data(json.dumps(data))
        return JsonResponse({
            "code": 0,
            "msg": result
        })
    except Exception, e:
        print 'call report : ', e
        return JsonResponse({
            "code": -1,
            "msg": u'通话上报失败'
        })


@require_http_methods(['GET'])
def call_report(request):
    """通话上报"""
    phone_num = request.GET.get('phone_num')
    apply_id = request.GET.get('apply_id')
    in_out = request.GET.get('in_out')
    person_num = request.GET.get('person_num')
    raw_data = request.GET.get('raw_data')
    report_type = request.GET.get('type')
    call_accept_id = request.GET.get('call_accept')

    raw_data_dict = json.loads(raw_data)

    call_accept_id_key = 'call_id_{}'.format(call_accept_id)
    if 'report_call_id' == report_type:
        redis_apply_id = redis_client.get(call_accept_id_key)
        if redis_apply_id:
            return JsonResponse({
                'code': 0,
                'msg': 'done'
            })
        redis_client.set(call_accept_id_key, apply_id)
        return JsonResponse({
            'code': 0,
            'msg': 'done'
        })

    r = redis_client.pipeline()
    r.get(call_accept_id_key)
    r.delete(call_accept_id_key)
    redis_apply_id = r.execute()[0]
    Log().info('apply id and call id: {0} --- {1}'.format(redis_apply_id, call_accept_id_key))
    if raw_data_dict['call_direction'] == 'inbound':
        _report_call_data(phone_num, in_out, request, '')
        return JsonResponse({
            'code': 0,
            'msg': 'ok'
        })
    elif redis_apply_id and raw_data_dict['call_direction'] == 'outbound':
        _report_call_data(phone_num, in_out, request, redis_apply_id)
        return JsonResponse({
            'code': 0,
            'msg': 'ok'
        })
