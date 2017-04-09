# -*- coding: utf-8 -*-
import datetime
import random

from django.conf import settings
from django.http import JsonResponse
from django.contrib.auth.models import User
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

from business_manager.employee.models import Employee
from business_manager.order.models import Captcha
from business_manager.review import message_client

msg_template = u"登陆验证码： {}【融数通】"

@csrf_exempt
@require_http_methods(['POST'])
def get_captcha(request):
    username = request.POST.get('username')
    if not username:
        return JsonResponse({
            "code": -1,
            "msg": u'参数错误'
        })
    return JsonResponse(_get_captcha(username))


def verify_captcha(captcha, username):
    # verify captcha
    print settings.ALLOW_VERIFY
    print captcha, username
    if settings.ALLOW_VERIFY:
        return True
    user = User.objects.filter(username=username)
    employee = Employee.objects.filter(user=user).first()
    # employee = Employee.objects.filter(user_id=request.user.id).first()
    if not employee:
        employee = Employee.objects.filter(mobile=username).first()
        if not employee:
            return False
    captcha_obj = Captcha.objects.filter(employee=employee).first()
    if captcha_obj:
        current = datetime.datetime.today()
        today = datetime.datetime.combine(current, datetime.datetime.min.time())
        tomorrow = today + datetime.timedelta(days=1)
        if captcha_obj.captcha == str(captcha).strip() and today <= captcha_obj.create_at < tomorrow:
            return True
        elif captcha_obj.create_at < today or captcha_obj.create_at >= tomorrow:
            return False    # expired captcha 
        else:
            return False    # wrong captcha 
    else:
        print("no captcha record")
        return False   # no captcha record, click to get captcha


def _get_captcha(username):
    employee = Employee.objects.filter(mobile=username).first()
    if not employee:
        user = User.objects.filter(username=username).first()
        employee = Employee.objects.filter(user=user).first()
        if not employee:
            return {'code': -1, 'msg': u'未找到对应用户'}
    phone = employee.mobile
    current = datetime.datetime.today()
    today = datetime.datetime.combine(current, datetime.datetime.min.time())
    tomorrow = today + datetime.timedelta(days=1)
    captcha_obj = Captcha.objects.filter(employee=employee).first()
    if not phone:
        return {'code': -1, 'msg': u'用户缺少手机号码'}
    if settings.ALLOW_VERIFY:
        return {'code': 0, 'msg': u'发送成功'}
    if captcha_obj and tomorrow > captcha_obj.create_at >= today:
        print('already send captcha, user: %s, captcha: %s' % (employee.username, captcha_obj.captcha))
        return {'code': -1, 'msg': u'验证码已发送'}
    else:
        new_captcha = random.randint(1000, 9999)
        # res = message_client.send_message(phone, msg_template.format(new_captcha).encode('utf-8'))
        res = message_client.send_message(phone, msg_template.format(new_captcha).encode('gbk'))
    print('send %s to %s result: %s' % (new_captcha, phone, res))
    if res:
        if captcha_obj:
            captcha_obj.create_at = current
            captcha_obj.captcha = new_captcha
            captcha_obj.save()
        else:
            Captcha.objects.create(employee=employee, captcha=new_captcha, create_at=current)
        return {'code': 0, 'msg': u'发送成功'}
    else:
        return {'code': -1, 'msg': u'发送失败'}
