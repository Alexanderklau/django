#!/usr/bin/env python
# coding=utf-8
import re

from django.http import JsonResponse
from django.db.models import Q
from django.views.decorators.http import require_http_methods

from business_manager.collection.views import CollectionDataProvider
from business_manager.employee.models import Employee, EmployeeGroup
from business_manager.config_center.models import WorkFlow, WorkStatus
from business_manager.order.apply_models import Apply
from business_manager.review.models import Review
from business_manager.employee.models import check_employee, get_employee_platform
from business_manager.util.permission_decorator import page_permission
from business_manager.util.tkdate import *

@require_http_methods(['GET'])
def get_review_status(request):
    """返回当前工作流所有审批状态"""
    platform = get_employee_platform(request)[0].name
    product = request.GET.get('product', '')
    wf = WorkFlow.objects.get(is_in_use=1, platform = platform, belong_product = product)
    wss = WorkStatus.objects.filter(workflow=wf)

    status_list = list()
    for ws in wss:
        status_list.append({
            'id': ws.id,
            'name': ws.other_name if ws.other_name else ws.name,
            'status_code': ws.status_code
        })

    return JsonResponse({
        'code': 0,
        'msg': u'返回状态成功',
        'data': status_list
    })


class ReviewDataProvider(CollectionDataProvider):
    """"""

    ORDERS = {
        'user_id': 'create_by__id',
        'name': 'create_by__name',
        'order_type': 'type',
        'channel': 'id',
        'created_at': 'create_at',
        'payment': 'amount',
        'compeleted_time': 'finish_time',
        'employee_name': 'owner_id',
        'status': 'status'
    }

    def object_filter(self, request=None, owner=None):
        """"""
        # print 'xxx: ', request.user
        query_owner = Q()
        if owner:
            try:
                _owner = Employee.objects.filter(user_id=request.user.id).first()
                if _owner:
                    query_owner = Q(owner_id=_owner.id)
            except Exception, e:
                print 'owner: ', e
      
        query_wf = Q()
        #wf = WorkFlow.objects.filter(is_in_use=1).first()
        #if wf:
        #    query_wf = Q(workflow=wf)

        status = request.GET.get('status')
        query_status = Q()
        
        if status:
            query_status = Q(status=status)

        time = request.GET.get('time')                                                                                                              
        start_time = end_time = None
        query_time = Q()          
        if 'today' == time:       
            start_time = get_today()
            end_time = get_tomorrow()
        elif 'yestoday' == time:  
            start_time = get_yestoday()
            end_time = get_today()
        elif 'toweek' == time:    
            start_time = get_first_day_of_week()
            end_time = get_tomorrow()
        elif 'tomonth' == time:   
            start_time = get_first_day_of_month()
            end_time = get_tomorrow()
        elif 'other' == time:     
            start_time = request.GET.get('start_time')
            end_time = request.GET.get('end_time')
                     
        if start_time and end_time:
            query_time = Q(create_at__lte=end_time, create_at__gte=start_time)

        platform_query = Q()
        user_platform = get_employee_platform(request)
        if len(user_platform) > 1:
            platform_param = request.GET.get('platform', '')
            if platform_param:
                platform_query = Q(platform = platform_param)
            else:
                platform_query = Q(platform__in = user_platform.values_list('name', flat = True))
        else:
            platform_query = Q(platform = user_platform[0].name)
        product_query = Q()
        product = request.GET.get('product', '')
        if product:
            product_query = Q(product = product)

        type_query = Q(type__in = ['0'])
        applies = Apply.objects.filter(query_wf, query_owner, query_time, query_status, platform_query, product_query, type_query)

        search = request.GET.get('search', '').strip()
        if search:
            return applies.filter(Q(create_by__name__contains=search) | Q(create_by__phone_no=search) | Q(create_by__id__contains=search) | Q(create_by__id_no=search))
        return applies

    def sort(self, request=None, queryset=None):
        """排序"""
        order_name, order_way = request.GET.get('order_name', '').strip(), request.GET.get('order_way', '').strip()
        if order_name and order_way:
            if 'asc' == order_way:
                return queryset.order_by(ReviewDataProvider.ORDERS.get(order_name, 'id'))
            elif 'desc' == order_way:
                return queryset.order_by('-' + ReviewDataProvider.ORDERS.get(order_name, 'id'))
        return queryset.order_by('-id')

    def genrate_result(self, request=None, owner=None):
        """"""
        self.platform = get_employee_platform(request)
        _applies = self.object_filter(request, owner=owner)
        sorted_applies = self.sort(request, _applies)
        applies = self.pagination(request, sorted_applies)
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
            _name = None
            if al.owner_type in [1, '1']:
                p = re.search(r'(\d+)', al.owner_id)
                if p:
                    eg = EmployeeGroup.objects.filter(pk=p.group(1)).first()
                    if eg:
                        _name = eg.group_name
            else:
                review = Review.objects.filter(order=al).order_by('-id').first()
                if review:
                    _name = review.reviewer.username
            data.append({
                'id': al.id,
                'user_id': al.create_by.id if al.create_by else 0,
                'name': al.create_by.name if al.create_by else '',
                'order_type': al.get_type_display(),
                'channel': 'saas',
                'created_at': al.create_at.strftime("%Y-%m-%d %H:%M:%S") if al.create_at else '',
                'compeleted_time': al.finish_time.strftime('%Y-%m-%d %H:%M:%S') if al.finish_time else '',
                'payment': al.amount,
                'employee_name': _name if _name else '',
                'status': status_name if status_name else al.get_status_display()
            })

        return {'code': 0, 'msg': u'返回审配列表成功', 'order_count': order_count, 'data': data}


@require_http_methods(['GET'])
@page_permission(check_employee)
def all_review_orders(request=None):
    """"""
    results = ReviewDataProvider().genrate_result(request)
    if isinstance(results, dict):
        return JsonResponse(results)
    return JsonResponse({
        'code': -1,
        'msg': u'返回审配列表失败'
    })

@require_http_methods(['GET'])
@page_permission(check_employee)
def my_review_orders(request=None):
    """"""
    results = ReviewDataProvider().genrate_result(request, True)
    if isinstance(results, dict):
        return JsonResponse(results)
    return JsonResponse({
        'code': -1,
        'msg': u'返回数据失败'
    })
