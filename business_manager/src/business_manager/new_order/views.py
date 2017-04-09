#!/usr/bin/env python
# coding=utf-8

import json
import time
import requests

from django.db.models import Q
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods

from business_manager.order.apply_models import Apply
from business_manager.config_center.models import WorkFlow, WorkStatus, ProfileFlow, ProfileModule
from business_manager.collection.views import CollectionDataProvider
from business_manager.order.models import User
from business_manager.review import user_center_client
from business_manager.config_center.models import LocationConf
from business_manager.employee.models import get_employee_platform, Platform
from business_manager.python_common.log_client import CommonLog as Log


@require_http_methods(['GET'])
def get_collect_status(request):
    """"""
    # order = .objects.filter(pk=request.GET.get('user_id')).first()
    user = get_object_or_404(User, pk=request.GET.get('user_id'))
    return JsonResponse({
        'code': 0,
        'msg': '',
        'data': {
            'on_off': user.is_report_location
        }
    })


@require_http_methods(['POST'])
@csrf_exempt
def on_or_off_location(request):
    """采集开关"""
    url = 'http://{0}:{1}/on_off/'.format(settings.WEB_HTTP_SERVER['HOST'], settings.WEB_HTTP_SERVER['PORT'])
    try:
        user = User.objects.get(pk=request.POST.get('user_id'))
        data = {
            'user_id': request.POST.get('user_id'),
            'platform': user.platform
        }
        r = requests.post(url=url, data=data, timeout=3)
        return JsonResponse({
            'code': 0,
            'msg': '完成切换',
            'data': r.content
        })
    except Exception, e:
        Log().error('In on_or_off_location -> {}'.format(e))
        return JsonResponse({
            'code': -1,
            'msg': str(e)
        })


@require_http_methods(['GET'])
def query_location_info(request):
    """获取用户某段时间地理位置信息"""
    url = 'http://{0}:{1}/query_location_info/'.format(settings.WEB_HTTP_SERVER['HOST'], settings.WEB_HTTP_SERVER['PORT'])
    _params = {
        'user_id': request.GET.get('user_id'),
        'start_time': request.GET.get('start_time'),
        'end_time': request.GET.get('end_time')
    }
    try:
        r = requests.get(url=url, params=_params)
        # print r.content
        return JsonResponse(r.json())
    except Exception, e:
        Log().error('In query_location_info -> {}'.format(e))
        return JsonResponse({
            'code': -1,
            'msg': str(e)
        })


@require_http_methods(['GET'])
def get_captcha(request):
    """获取验证码接口"""
    url = 'http://{0}:{1}/get_captcha'.format(settings.WEB_HTTP_SERVER['HOST'], settings.WEB_HTTP_SERVER['PORT'])
    try:
        r = requests.get(url=url, data=request.body, timeout=3)
        if 200 == r.status_code:
            return JsonResponse(r.json())
        return JsonResponse({
            "code": -1,
            "msg": r.content
        })
    except Exception, e:
        return JsonResponse({
            "code": -1,
            "msg": str(e)
        })


@require_http_methods(['POST'])
@csrf_exempt
def commit_common_accounts(request):
    """通用账号信息提交"""
    url = 'http://{0}:{1}/submit_info_for_crawl'.format(settings.WEB_HTTP_SERVER['HOST'], settings.WEB_HTTP_SERVER['PORT'])
    try:
        _data = json.loads(request.body)
        _data.update({
            "org_account": settings.DATA_SERVER['ORG_NAME'], 
            "service_id": settings.DATA_SERVER['SERVICE_ID']
        })
        print '****post data: ', _data
        r = requests.post(url=url, data=json.dumps(_data), timeout=3)
        # print 'content : ', r.status_code, r.content
        if 200 == r.status_code:
            print '-*-request result-*-'
            data = json.loads(request.body)
            _url = 'http://{0}:{1}/fetch_crawl_result'.format(settings.WEB_HTTP_SERVER['HOST'], settings.WEB_HTTP_SERVER['PORT'])
            _params = {
                "uin": data.get("uin"), 
                "string_selected_data": data.get("string_selected_data"), 
                "int32_module_id": data.get("int32_module_id")
            }

            _count = 0
            while True:
                if _count > 20:
                    break
                time.sleep(6)
                _count += 1
                r = requests.get(url=_url, params=_params, timeout=3)
                print 'result:', r.content 
                content = r.json().get('logic_rsp')
                if content and content.get('int32_retcode') > -1:
                    return JsonResponse(r.json())
                else:
                    print r.json()
            return JsonResponse({'code': -1, 'msg': u'爬取超时，请重试'})
    except Exception, e:
        return JsonResponse({'code': -1, 'msg': str(e)})


def zm_business(request=None, url=None):
    """芝麻授权转发业务"""
    if request and url:
        try:
            # print '***params: ', request.body
            _data = json.loads(request.body)
            _data.update({
                "org_account": settings.DATA_SERVER['ORG_NAME'], 
                "service_id": settings.DATA_SERVER['SERVICE_ID']
            })
            print _data
            r = requests.post(url=url, data=json.dumps(_data), timeout=3)
            print '***response:', r.content
            content = r.json()
            if content.get('authorized'):
                print '->authorized: ', content.get('authorized')
                # _user_id = _data.get('user_id')
                try:
                    _user_id = content['biz_state']['uin']
                    print 'user id: ', _user_id
                    _module_id = _data.get('module_id')
                    if _user_id:
                        _user = User.objects.get(pk=_user_id)
                        _state_info = json.loads(_user.submit_modules_state)
                        flow_id = _state_info.get('current_flow')
                        info = {
                            'user_id': int(_user_id), 
                            'flow_module_id': int(_module_id), 
                            'flow_id': int(flow_id)
                        }
                        print '---> info:', info 
                        user_center_client.edit_basic_profile(info, None, None, None)
                except Exception, e:
                    print e
            return {
                "code": 0,
                "msg": u"",
                "content": r.json()
            }
        except Exception, e:
            return {
                "code": -1,
                "msg": str(e),
                "content": dict()
            }
    return {
        "code": -1,
        "msg": u"请求出错",
        "content": dict()
    }

@require_http_methods(['POST'])
@csrf_exempt
def zm_fun(request, path=None):
    """"""
    _url = settings.DATA_SERVER['URL'] + '/' + path
    data = zm_business(request, _url)
    return JsonResponse(data)

@require_http_methods(['POST'])
@csrf_exempt
def zm_srouce(request):
    """查询芝麻分"""
    _url = settings.DATA_SERVER['URL'] + 'query_data'
    data = zm_business(request, _url)
    return JsonResponse(data)


@require_http_methods(['POST'])
@csrf_exempt     
def zm_result(request):
    """获取芝麻授权接口"""
    _url = settings.DATA_SERVER['URL'] + 'zmxy_auth_status'
    data = zm_business(request, _url)
    return JsonResponse(data)

@require_http_methods(['POST'])
@csrf_exempt
def zm_auth(request):
    """芝麻授权功能"""
    _url = settings.DATA_SERVER['URL'] + 'zmxy_auth'
    data = zm_business(request, _url)
    return JsonResponse(data)

class NewOrderDataProvider(CollectionDataProvider):
    """进件订单列表"""

    ORDERS = {
        'order_id': 'id',
        'username': 'create_by__name',
        'created_at': 'create_at', 
        'status': 'status'
    }
    
    def object_filter(self, request=None):
        """"""
        wf = WorkFlow.objects.filter(is_in_use=1)
        platform_query = Q()
        user_platform = get_employee_platform(request)
        print 'user_platform -> ', user_platform
        if len(user_platform) > 1:
            platform_param = request.GET.get('platform', '')
            if platform_param:
                platform_query = Q(platform = platform_param)
            else:
                platform_query = Q(platform__in = user_platform.values_list('name'))
        else:
            platform_query = Q(platform = user_platform[0].name)
        product = request.GET.get('product', '')
        product_query = Q()
        if product:
            product_query = Q(product = product)
        applies = Apply.objects.filter(Q(workflow__in=wf) & platform_query & product_query).filter(Q(type='0') | Q(type='s1'))
        search = request.GET.get('search', '').strip()
        if search:
            return applies.filter(Q(create_by__name__contains=search) | Q(id__contains=search) | Q(create_by__phone_no=search) | Q(create_by__id_no=search))
        return applies

    def sort(self, request=None, queryset=None):
        """排序"""                   
        order_name, order_way = request.GET.get('order_name', '').strip(), request.GET.get('order_way', '').strip()
        if order_name and order_way:                                                                                                                
            if 'asc' == order_way:   
                return queryset.order_by(NewOrderDataProvider.ORDERS.get(order_name, 'id'))
            elif 'desc' == order_way:
                return queryset.order_by('-' + NewOrderDataProvider.ORDERS.get(order_name, 'id'))
        return queryset.order_by('-id')

    def genrate_result(self, request=None, owner=False):
        """生成结果"""
        _applies = self.object_filter(request)
        print '--->', _applies.count()
        sorted_applies = self.sort(request, _applies)
        applies = self.pagination(request, sorted_applies)
        print 'pagination result: ', applies
        order_count = _applies.count()

        data = list()
        for al in applies:
            status_name = None
            if al.status != 'r':
                current_status = WorkStatus.objects.filter(Q(workflow_id=al.workflow_id) & Q(status_code=al.status)).first()
                if current_status:
                    status_name = current_status.other_name if current_status.other_name else current_status.name
                else:
                    status_name = u'打回修改'
            has_location_module = 0
            is_on = 0
            lo = LocationConf.objects.filter(platform=al.platform).first()
            if lo:
                is_on = lo.is_on

            flow = ProfileFlow.objects.filter(pk=al.flow_id).first()
            modules = ProfileModule.objects.filter(show_name=u'地理信息')
            # print 'module --> ', module
            if modules and flow:
                # print flow.required_modules
                for module in modules:
                    if str(module.id) in flow.required_modules:
                        has_location_module = 1
                        break
            on_off = (is_on and has_location_module and al.create_by.is_report_location)
            # print 'on_off --> ', on_off
            data.append({
                'id': al.id,
                'user_id': al.create_by.id,
                'name': al.create_by.name if al.create_by else '',
                'created_at': al.create_at.strftime('%Y-%m-%d %H:%M:%S') if al.create_at else '',
                'status': status_name if status_name else al.get_status_display(),
                # 'on_off': al.create_by.is_report_location,
                # 'has_location_module': 1
                'on_off': on_off,
                'has_location_module': has_location_module
            })

        return {'code': 0, 'msg': u'返回成功', 'order_count': order_count, 'data': data}


def get_applies(request=None):
    """"""
    results = NewOrderDataProvider().genrate_result(request)
    if isinstance(results, dict):
        return JsonResponse(results)
    return JsonResponse({
        "code": -1,
        "msg": u'返回失败',
        'data': []
    })
