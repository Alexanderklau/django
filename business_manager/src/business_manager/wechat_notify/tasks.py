# -*- coding:utf-8 -*-
from __future__ import absolute_import

import json
from datetime import datetime, timedelta
import requests

from django.core.cache import cache
from django.conf import settings

from business_manager.celery import app
from business_manager.order.apply_models import Apply
from business_manager.util.wechat_notify_util import gen_key
from business_manager.employee.models import get_dispatch_collector_list
from business_manager.wechat_notify.views import wechat_get_recently_applys

NOTIFY_TIME = 30  # 提前提醒时间
NOTIFY_URL = "http://{}:{}/rst/sendmessage".format(settings.WECHAT_SERVER.get('HOST'),
                                                   settings.WECHAT_SERVER.get('PORT'))
TEXT_TYPE = 1
AGENT_ID = 'dingdangcuishou'
NOTIFY_GROUP = 'dingdangcuishou'
MSG_TEMPLATE = '订单号：{}，承诺还款时间：{}，姓名：{}'
MSG_HEAD = '以下订单的承诺还款时间即将在{}分钟后到期：'.format(NOTIFY_TIME)

COLLECTION_STATUS = (
                     Apply.COLLECTION,
                     Apply.PROCESSING
                     )


@app.task
def check_applys():
    print("in check_applies")
    notify_applies = get_notify_applies_from_db()
    employee_apps = convert_employee_apps(notify_applies)
    for username, apps in employee_apps.iteritems():
        print("notify apply:")
        notify_employee(username, apps)
    print("out check_applies")


@app.task
def notice_transfer_apply():
    print("in notice transfer apply")
    employees = get_dispatch_collector_list()
    for employee in employees:
        msg = wechat_get_recently_applys(employee.user.username)
        send_wechat_msg(employee.user.username, msg)
    print("out notice transfer apply")


def get_notify_applys():
    current = datetime.now()
    keys = []
    for n in range(NOTIFY_TIME):
        temp_datetime = current + timedelta(minutes=n)
        keys.append(temp_datetime)
    values = []
    for key in keys:
        key = gen_key(key, "*")
        print("key: %s" % key)
        value = cache.keys(key)
        print("key:", key, "value:", value)
        values += value
    print("values: %s" % values)
    values = [val.split("_")[-1] for val in values]
    notify_applys = Apply.objects.filter(id__in=values)
    return notify_applys


def get_notify_applies_from_db():
    current = datetime.now()
    end_time = current + timedelta(minutes=NOTIFY_TIME)
    applies = Apply.objects.filter(promised_repay_time__gte=current,
                                   promised_repay_time__lt=end_time,
                                   status__in=COLLECTION_STATUS,
                                   employee__isnull=False)
    return applies


def notify_employee(username, apps):
    print("in notify employee, user: %s, applies:" % username, apps)
    msg = MSG_HEAD + ', '.join([MSG_TEMPLATE.format(str(app.repayment.order_number),
                                                    app.promised_repay_time.strftime("%Y-%m-%d %H:%M"),
                                                    app.repayment.user.name.encode('utf-8'))
                                for app in apps])
    # username = "liukai"
    print("send msg: %s to %s" % (msg, username))
    params = {
        "content": msg,
        "msg_type": TEXT_TYPE,
        "agentid": AGENT_ID,
        "from_who": NOTIFY_GROUP,
        "tousers": str([username])
    }
    res = requests.get(NOTIFY_URL, params=params)
    print(res.text)
    if res.status_code == 200 and res.json()['errcode'] == 0:
        print(res.json())
        print("send success")
        # for app in apps:
        #     key = gen_key(app.promised_repay_time, app.id)
        #     cache.delete_pattern(key)


def convert_employee_apps(apps):
    ret = {}
    for app in apps:
        print("app: %s" % app)
        if app.employee:
            username = app.employee.user.username
        else:
            username = 'liukai'
        if ret.get(username):
            ret[username].append(app)
        else:
            ret[username] = [app]
    return ret


def send_wechat_msg(user, msg):
    # user = 'liukai'
    params = {
        "content": msg,
        "msg_type": TEXT_TYPE,
        "agentid": AGENT_ID,
        "from_who": NOTIFY_GROUP,
        "tousers": str([user])
    }
    res = requests.get(NOTIFY_URL, params=params)
    print(res.text)
    if res.status_code == 200 and res.json()['errcode'] == 0:
        print(res.json())
        print("send success")
