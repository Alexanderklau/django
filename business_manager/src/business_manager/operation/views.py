#!/usr/bin/env python
# coding=utf-8

import json
import uuid

from datetime import datetime

from django.db.models import Q
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods

from business_manager.strategy.models import Strategy2
from business_manager.employee.models import Employee, get_employee_platform
from business_manager.order.apply_models import Apply
from business_manager.collection.report import report_collection
from business_manager.collection.models import InstallmentDetailInfo
from business_manager.operation.general_views import get_realtime_repay_result, get_should_repay_periods
from business_manager.util.tkdate import get_today, get_tomorrow, get_yestoday, get_first_day_of_week, get_first_day_of_month


sort_dict = {
    'id': 'id',
    'amount': 'repayment__apply_amount',
    'repay_amount': 'repayment__exact_amount',
    'bank_name': 'repayment__bank_card__bank_name',
    'apply_time': 'repayment__apply_time',
    'payment': 'repayment__apply_amount',
}


def withhold_status(request, uri=None):
    """"""
    if 'withhold_status' == uri:
        status = [{'status_code': 'check_failed', 'name': u'复核失败'}, {'status_code': 'wait_repay', 'name': u'等待扣款'}, {'status_code':'wait_check', 'name': u'待复核'}, {'status_code': 'repay_failed', 'name': u'扣款失败'}, {'status_code': 'part_success', 'name': u'部分成功'}, {'status_code': 'repay_success', 'name': u'扣款成功'}, {'status_code': 'overdue', 'name': u'已逾期'}]
    elif 'paid_status' == uri:
        status = [{'status_code': 'prepayed', 'name': u'等待放款'}, {'status_code': 'failed', 'name': u'打款失败'}, {'status_code': 'success', 'name': u'打款成功'}]
    return JsonResponse({
        'code': 0,
        'msg': u'返回状态列表成功',
        'data': status
    })


def get_current_period(order=None, status_list=[2, ]):
    """获取给定订单当前期数"""
    installments = InstallmentDetailInfo.objects.filter(repayment=order.repayment,) 
    return get_should_repay_periods(order)


class DataProvider(object):
    """列表基类"""
    
    def objects_filter(self, request=None):
        """筛选条件"""
        pass

    def search(self, query_set=None, request=None):
        """"""
        if query_set and request:
            search = request.GET.get('search', '').strip()
            if search:
                query_search_id_query = Q()
                try:
                    search_id = int(search)
                    query_search_id_query = Q(pk=search_id)
                except:
                    pass
                applies = query_set.filter(query_search_id_query | Q(create_by__phone_no=search) | Q(repayment__order_number=search) | Q(create_by__id_no=search) | Q(repayment__user__name__icontains=search))
                return applies
            return query_set
        return []

    def sort(self, query_set=None, request=None):
        """"""
        order_name = request.GET.get('order_name', '').strip()
        order_name = sort_dict.get(order_name)
        if query_set and request:
            order_way = request.GET.get('order_way', '').strip()
            # order_name, order_way = request.GET.get('order_name', '').strip(), request.GET.get('order_way', '').strip()
            if order_name and order_way:
                if 'asc' == order_way:
                    return query_set.order_by(order_name)
                elif 'desc' == order_way:
                    return query_set.order_by('-' + order_name)
                else:
                    return query_set.order_by('-id')
            return query_set.order_by('-id')
        return []

    def pagination(self, query_set=None, request=None):
        """"""
        if query_set and request:
            page, page_size = request.GET.get('page', '').strip(), request.GET.get('page_size', '').strip()
            # paginator = Paginator(query_set, 15)
            if page_size:
                paginator = Paginator(query_set, page_size)
            else:
                paginator = Paginator(query_set, 15)
            if page:
                return paginator.page(page)
            else:
                return paginator.page(1)
        return query_set

    def genrate_result(self, request=None):
        """"""
        pass


def time_filter(request=None, field='create_at'):
    """"""
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
        dic = {
            '%s__lte' % field: end_time,
            '%s__gte' % field: start_time,

        }
        query_time = Q(**dic)
        # query_time = Q(create_at__lte=end_time, create_at__gte=start_time)  # 订单创建时间
        # query_time = Q(repayment__next_repay_time__lte=end_time, repayment__next_repay_time__gte=start_time)  # 下次还款时间

    return query_time


class RepayOrders(DataProvider):
    """代扣列表"""

    def objects_filter(self, request=None):
        """"""
        # status condition.
        query_status = Q()
        _status = request.GET.get('order_status', 'all').strip()

        if 'wait_repay' == _status:
            query_status = Q(status='0')
        elif 'repay_success' == _status:
            query_status = Q(status__in=['8', '9'])
        elif 'repay_failed' == _status:
            query_status = Q(status='c') | Q(status='o')
        elif 'part_success' == _status:
            query_status = Q(status='d')
        elif 'overdue' == _status:
            query_status = ~Q(status='9')
        elif 'wait_check' == _status:
            query_status = Q(status='k')
        elif 'check_failed' == _status:
            query_status = Q(status='t')

        query_time = time_filter(request, 'should_repay_time')
        # 已逾期: 除了 成功的 单子, 其他所有的订单只要逾期.都归类到已逾期
        q_overdue_days = Q(overdue_days=0)
        if 'overdue' == _status:
            q_overdue_days = Q(overdue_days__gte=1)
        elif _status in ['', 'part_success', 'repay_success']:
            q_overdue_days = Q()

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


        # return Apply.objects.filter(query_time & query_status & Q(type__in=['p', 'a', 'b', 'c', 'd', 'e', 'g', 'h']) & ~Q(repayment=None))
        return Apply.objects.filter(q_overdue_days, query_time & query_status & Q(type__in=['p']) & ~Q(repayment=None) & platform_query & product_query)

    @classmethod
    def get_current_period(cls, apply):
        """"""
        periods = list()
        zero_installment = InstallmentDetailInfo.objects.filter(repayment=apply.repayment, installment_number=0, repay_status__in=[1, 2]).first()
        if zero_installment:
            periods.append(zero_installment.installment_number)

        installments = InstallmentDetailInfo.objects.filter(Q(repayment=apply.repayment) & Q(installment_number__gte=(apply.money+1)))
        for install in installments:
            if install.repay_status == 3 or install.repay_status == 8:
                periods.append(install.installment_number)
            elif install.repay_status == 7:
                break
            else:
                periods.append(install.installment_number)
        return periods

    def genrate_result(self, request=None):
        """生成结果"""
        _rows = self.objects_filter(request)

        search_results = self.search(_rows, request)
        sort_results = self.sort(search_results, request)
        applies = self.pagination(sort_results, request)
        order_count = 0
        if search_results:
            order_count = search_results.count()

        results = list()
        for al in applies:
            apply_first_ins = InstallmentDetailInfo.objects.filter(installment_number=al.money + 1, repayment=al.repayment).first()

            installments = InstallmentDetailInfo.objects.filter(Q(repayment=al.repayment) & Q(installment_number__in = RepayOrders.get_current_period(al)))
            current_peroids = 1
            if installments.first() and installments.first().installment_number > 0:
                if al.status in [3, 8, 9, '3', '8', '9']:
                    current_peroids = al.money + 1
                else:
                    current_peroids = installments.first().installment_number + installments.count() - 1
            last_installment = InstallmentDetailInfo.objects.filter(installment_number=current_peroids, repayment=al.repayment).first()
            first_install = InstallmentDetailInfo.objects.filter(repayment=al.repayment).order_by('installment_number').first()
            getpay_time = al.repayment.first_repay_day
            getpay_time = getpay_time.strftime('%Y-%m-%d') if getpay_time else ''

            status_name = u'其它'
            if al.overdue_days > 0 and al.status not in ['9', '8']:
                status_name = u'已逾期'
            else:
                if al.status == '0':
                    status_name = u'等待扣款'
                elif al.status in ['c', 'o']:
                    status_name = u'扣款失败'
                elif al.status == 'd':
                    status_name = u'部分成功'
                elif al.status == 'k':
                    status_name = u'待复核'
                elif al.status == '9':
                    status_name = u'扣款成功'
                elif al.status == 't':
                    status_name = u'复核失败'
            
            _strategy = Strategy2.objects.filter(strategy_id=al.repayment.strategy_id).first()
            strategy = u'{}个月'.format(al.repayment.installment_count)
            if _strategy:
                if _strategy.installment_type == 1:
                    strategy = u'{}个月'.format(_strategy.installment_count)
                elif _strategy.installment_type == 2:
                    strategy = u'{}天'.format(_strategy.installment_days)
            is_withhold = 0
            if status_name in [u'已逾期']:
                is_withhold = 2
            elif status_name in [u'待复核', u'扣款成功']:
                is_withhold = 1

            bank_name = ''
            bank_card = al.repayment.bank_card
            if bank_card:
                bank_name = bank_card.bank_name
            results.append({
                'id': al.id,
                'user_id': al.create_by.id,
                'order_number': al.repayment.order_number,
                'name': al.create_by.name,
                'id_no': al.create_by.id_no,
                'amount': al.repayment.apply_amount,
                'repay_amount': al.repayment.exact_amount,
                # 'strategy': _strategy.strategy_name if _strategy else u'{}个月'.format(al.repayment.installment_count),
                'strategy': strategy,
                'bank_name': bank_name,
                'apply_time': al.repayment.apply_time.strftime('%Y-%m-%d') if al.repayment.apply_amount else '', 
                'getpay_time': getpay_time,
                'withhold_time': last_installment.should_repay_time.strftime('%Y-%m-%d') if last_installment and last_installment.should_repay_time else '',
                'status': status_name if status_name else '',
                'current_peroids': al.money + 1,
                'is_withhold': is_withhold,
                'should_repay_time': apply_first_ins.should_repay_time.strftime('%Y-%m-%d'),
            })
        return results, order_count


def withhold_orders(request):
    """代扣订单实例化"""
    rows, count = RepayOrders().genrate_result(request)
    return JsonResponse({
        'code': 0,
        'msg': u'返回列表成功',
        'order_count': count,
        'data': rows
    })


class PayOrders(DataProvider):
    """代付"""

    def objects_filter(self, request=None):
        """"""
        query_status = Q()
        _status = request.GET.get('order_status', 'all').strip()

        if 'prepayed' == _status:
            query_status = Q(status__in=['0', 's'])
        elif 'failed' == _status:
            query_status = Q(status='p3')
        elif 'success' == _status:
            query_status = Q(status='p2')

        query_time = time_filter(request)

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

        return Apply.objects.filter(query_time & query_status & Q(type='l') & ~Q(repayment=None) & platform_query & product_query)

    def genrate_result(self, request):
        """"""
        _rows = self.objects_filter(request)
        search_results = self.search(_rows, request)
        sort_results = self.sort(search_results, request)
        applies = self.pagination(sort_results, request)
        order_count = 0
        if search_results:
            order_count = search_results.count()

        results = list()
        for o in applies:
            try:
                if o.status in ['0', 's']:
                    status_name = u'等待放款'
                elif o.status in ['p2']:
                    status_name = u'打款成功'
                elif o.status in ['p3']:
                    status_name = u'打款失败'
                else: 
                    status_name = ''
                # repay = o.repayment
                # _strategy = Strategy2.objects.filter(strategy_id=o.repayment.strategy_id).first()
                _strategy = Strategy2.objects.filter(strategy_id=o.repayment.strategy_id).first()
                strategy = u'{}个月'.format(o.repayment.installment_count)
                if _strategy:                  
                    if _strategy.installment_type == 1:
                        strategy = u'{}个月'.format(_strategy.installment_count)
                    elif _strategy.installment_type == 2:
                        strategy = u'{}天'.format(_strategy.installment_days)
                results.append({
                    'id': o.id,
                    'user_id': o.create_by.id,
                    'order_number': o.repayment.order_number,
                    'name': o.create_by.name,
                    'id_no': o.create_by.id_no,
                    'channel': o.repayment.get_capital_channel_id_display() or '',
                    'amount': o.repayment.apply_amount,
                    'repay_amount': 0 if status_name in [u'等待放款', u'打款失败'] else o.repayment.exact_amount,
                    # 'strategy':  _strategy.name if _strategy else u'{}个月'.format(o.repayment.installment_count),
                    'strategy': strategy,
                    'bank_name': o.repayment.bank_card.bank_name,
                    'apply_time': o.repayment.apply_time.strftime('%Y-%m-%d') if o.repayment.apply_time else '',
                    'getpay_time': o.repayment.first_repay_day.strftime('%Y-%m-%d') if status_name in [u'打款成功'] and o.repayment.first_repay_day else '',
                    'status': status_name,
                    'is_paid': 0 if o.status in ['0', 's', 'p3'] else 1
                })
            except:
                 print 'In get_paid_orders add list failed -> ', o
        return results, order_count


def paid_orders(request):
    """"""
    results, count = PayOrders().genrate_result(request)
    return JsonResponse({
        'code': 0,
        'msg': u'返回代付订单列表成功', 
        'order_count': count,
        'data': results
    })


@require_http_methods(['GET'])
def get_withhold_orders(request):
    """代扣订单列表信息拉取"""
    order_ids = request.GET.get('order_ids')
    order_ids = order_ids[1:-1].split(',')
    if isinstance(order_ids, list):
        results = list()
        # for al in orders:
        for _pk in order_ids:
            al = Apply.objects.filter(pk=_pk).first()
            if not al:
                continue
            apply_first_ins = InstallmentDetailInfo.objects.filter(installment_number=al.money + 1, repayment=al.repayment).first()

            installments = InstallmentDetailInfo.objects.filter(Q(repayment=al.repayment) & Q(installment_number__in = RepayOrders.get_current_period(al)))
            current_peroids = 1
            if installments.first() and installments.first().installment_number > 0:
                if al.status in [3, 8, 9, '3', '8', '9']:
                    current_peroids = al.money + 1
                else:
                    current_peroids = installments.first().installment_number + installments.count() - 1
            last_installment = InstallmentDetailInfo.objects.filter(installment_number=current_peroids).first()
            first_install = InstallmentDetailInfo.objects.filter(repayment=al.repayment).order_by('installment_number').first()
            getpay_time = al.repayment.first_repay_day
            getpay_time = getpay_time.strftime('%Y-%m-%d') if getpay_time else ''
            #getpay_time = ''
            #if first_install:
            #    getpay_time = first_install.should_repay_time.strftime('%Y-%m-%d') if first_install.should_repay_time else ''
            

            if al.type == 'p':
                if al.overdue_days > 0 and al.status not in ['9', '8']:
                # today = datetime.today().strftime('%Y-%m-%d')
                # if al.repayment.overdue_days > 0 and al.repayment.next_repay_time and al.repayment.next_repay_time.strftime('%Y-%m-%d') != today:
                    status_name = u'已逾期'
                else:
                    if al.status == '0':
                        status_name = u'等待扣款'
                    elif al.status in ['c', 'o']:
                        status_name = u'扣款失败'
                    elif al.status == 'd':
                        status_name = u'部分成功'
                    elif al.status == 'k':
                        status_name = u'待复核'
                    elif al.status == '9':
                        status_name = u'扣款成功'
                    #else:
                    #    status_name = u'已逾期'

            # _strategy = Strategy2.objects.filter(strategy_id=al.repayment.strategy_id).first()
            _strategy = Strategy2.objects.filter(strategy_id=al.repayment.strategy_id).first()
            strategy = u'{}个月'.format(al.repayment.installment_count)
            if _strategy:                  
                if _strategy.installment_type == 1:
                    strategy = u'{}个月'.format(_strategy.installment_count)
                elif _strategy.installment_type == 2:
                    strategy = u'{}天'.format(_strategy.installment_days)

            results.append({
                'id': al.id,
                'user_id': al.create_by.id,
                'order_number': al.repayment.order_number,
                'name': al.create_by.name,
                'id_no': al.create_by.id_no,
                'amount': al.repayment.apply_amount,
                'repay_amount': al.repayment.exact_amount,
                # 'strategy': _strategy.name if _strategy else u'{}个月'.format(al.repayment.installment_count),
                'strategy': strategy,
                'bank_name': al.repayment.bank_card.bank_name,
                'apply_time': al.repayment.apply_time.strftime('%Y-%m-%d') if al.repayment.apply_amount else '', 
                'getpay_time': getpay_time,
                'withhold_time': last_installment.should_repay_time.strftime('%Y-%m-%d') if last_installment else '',
                'status': status_name if status_name else '',                                                                                     
                'current_peroids': al.money + 1,
                'is_withhold': 0 if al.status in ['3', '8', '9'] else 1,
                'should_repay_time': apply_first_ins.should_repay_time.strftime('%Y-%m-%d'),
            })
        return JsonResponse({
            'code': 0,
            'msg': u'返回代扣列表信息成功',
            'data': results
        })
    return JsonResponse({
        'code': -1,
        'msg': u'参数错误'
    })

@require_http_methods(['GET'])
def batch_repay_loan(request):
    """批量扣款接口"""
    ids = request.GET.get('order_ids')
    channel = request.GET.get('channel')
    repay_type = request.GET.get('type')
    notes = request.GET.get('notes')
    try_to_amount = 0
    
    ids = ids[1:-1].split(',')
    
    staff = get_object_or_404(Employee, user=request.user)
    # staff = get_object_or_404(Employee, pk=59)
    order_repay_status = list()
    error_ids = []
    for _id in ids:
        try:
            order = Apply.objects.filter(pk=_id).first()
            if not order:
                order_repay_status.append({_id: 0})
                continue
            msg = get_realtime_repay_result(order, repay_type, try_to_amount, channel, staff)
            
            # 扣款上报
            _order = Apply.objects.filter(pk=_id).first()  # 避免使用缓存
            try:
                report_collection(_order)
            except:
                pass 
            if '扣款过程正常' in msg:
                _order.real_repay_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                _order.save()
                order_repay_status.append({'id': _id, 'status': 1})
            else: 
                error_ids.append(_id)
                order_repay_status.append({'id': _id, 'status': 0})
        except Exception, e:
            print 'In batch_repay_loan: ', e
    msg = u'批量扣款 成功'
    if error_ids:
        msg = u'共 %s 个订单 扣款失败.订单号: %s' % (len(error_ids), ', '.join(error_ids))
    return JsonResponse({
        'code': 0,
        'msg': msg,
        'data': order_repay_status
    })


@require_http_methods(['GET'])
def pay_modal_info(request, pk=None):
    """拉取用户贷款信息接口"""
    order = Apply.objects.filter(pk=pk).first()
    if not order:
        return JsonResponse({
            'code': -1,
            'msg': u'参数出错',
            'data': dict()
        })
    # _strategy = Strategy2.objects.filter(strategy_id=order.repayment.strategy_id).first()
    
    _strategy = Strategy2.objects.filter(strategy_id=order.repayment.strategy_id).first()
    strategy = u'{}个月'.format(order.repayment.installment_count)                                                                           
    if _strategy:                  
        if _strategy.installment_type == 1:
            strategy = u'{}个月'.format(_strategy.installment_count)
        elif _strategy.installment_type == 2:
            strategy = u'{}天'.format(_strategy.installment_days)

    data = {
        'name': order.create_by.name,
        'phone_number': order.create_by.phone_no,
        'id_no': order.create_by.id_no,
        'amount': order.repayment.apply_amount,
        'repay_amount': order.repayment.exact_amount,
        # 'strategy':  _strategy.name if _strategy else u'{}个月'.format(order.repayment.installment_count),
        'strategy': strategy,
        'bank_no': order.repayment.bank_card.card_number,
        'bank_name': order.repayment.bank_card.bank_name
    }

    return JsonResponse({
        'code': 0,
        'msg': u'返回基本信息成功',
        'data': data
    })


@require_http_methods(['GET'])
def get_paid_orders(request):
    """拉取代付订单列表"""
    # ids = json.loads(request.body).get('order_ids')
    ids = request.GET.get('order_ids')[1:-1].split(',')
    if not ids:
        return JsonResponse({
            'code': -1,
            'msg': u'参数错误',
            'data': {}
        })
    orders = Apply.objects.filter(pk__in=ids)
    data = list()
    for o in orders:
        try:
            if o.status in ['0', 's']:
                status_name = u'等待放款'
            elif o.status in ['p2']:
                status_name = u'打款成功'
            elif o.status in ['p3']:
                status_name = u'打款失败'
            else: 
                status_name = ''
            # repay = o.repayment
            # _strategy = Strategy2.objects.filter(strategy_id=o.repayment.strategy_id).first()
            _strategy = Strategy2.objects.filter(strategy_id=o.repayment.strategy_id).first()
            strategy = u'{}个月'.format(o.repayment.installment_count)                                                                           
            if _strategy:                  
                if _strategy.installment_type == 1:
                    strategy = u'{}个月'.format(_strategy.installment_count)
                elif _strategy.installment_type == 2:
                    strategy = u'{}天'.format(_strategy.installment_days)

            data.append({
                'id': o.id,
                'user_id': o.create_by.id,
                'order_number': o.repayment.order_number,
                'name': o.create_by.name,
                'id_no': o.create_by.id_no,
                'channel': o.repayment.get_capital_channel_id_display() or '',
                'amount': o.repayment.apply_amount,
                'repay_amount': 0 if status_name in [u'等待放款', u'打款失败'] else o.repayment.exact_amount,
                # 'strategy':  _strategy.name if _strategy else u'{}个月'.format(o.repayment.installment_count),
                'strategy': strategy,
                'bank_name': o.repayment.bank_card.bank_name,
                'apply_time': o.repayment.apply_time.strftime('%Y-%m-%d') if o.repayment.apply_time else '',
                # 'getpay_time': o.repayment.first_repay_day.strftime('%Y-%m-%d') if o.repayment.first_repay_day else '',
                'getpay_time': '',
                'status': status_name,
                'is_paid': 0 if o.status in ['0', 's', 'p3'] else 1
            })
        except:
            print 'In get_paid_orders add list failed -> ', o
    token = uuid.uuid1().hex
    return JsonResponse({
        'code': 0,
        'msg': u'返回列表成功',
        'token': token,
        'data': data
    })


@require_http_methods(['GET'])
def comfirm_pay_status(request):
    """预留打款失败接口"""
    order = Apply.objects.filter(pk=request.GET.get('apply_id')).first()
    order.status = Apply.PAY_FAILED
    order.save()
    return JsonResponse({
        'code': 0,
        'msg': u'确认 打款失败'
    })

