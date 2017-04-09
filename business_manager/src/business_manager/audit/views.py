# -*- coding: utf-8 -*-
# import re
import os

from datetime import datetime
from openpyxl import Workbook

from django.db.models import Q
from django.core.servers.basehttp import FileWrapper
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.http import require_http_methods
from django.conf import settings

from business_manager.employee.models import get_employee_platform
from business_manager.strategy.models import Strategy2
from business_manager.order.apply_models import Apply, CheckApply
from business_manager.operation.views import DataProvider, time_filter
from business_manager.collection.models import InstallmentDetailInfo
from business_manager.python_common.log_client import CommonLog as Log
from business_manager.util.tkdate import get_today, get_tomorrow, get_yestoday, get_first_day_of_week, get_first_day_of_month

sort_dict = {
    'order_number': 'repayment__order_number',
    'id_no': 'repayment__user__id_no',
    'should_repay_time': 'should_repay_time',
    'strategy': 'repayment__installment_count',
    'loan_series': 'installment_number',
    'salary': 'repay_fee',
    'id': 'id',
    'repay_type': 'type',
    'created_at': 'create_at',
    'finish_time': 'finish_time',
    'compeleted_time': 'status'
}


@require_http_methods(['GET'])
def get_status(request, path=None):
    """"""
    data = list()
    if 'check_repay_status' == path:
        data = [
        #{
        #    'status_code': 'all', 
        #    'name': u'所有'
        #},
           {
            'status_code': 'waiting', 
            'name': u'等待复核'
        }, {
            'status_code': 'success',
            'name': u'复核成功'
        }, {
            'status_code': 'failed',
            'name': u'复核失败'
        }]
        return JsonResponse({
            'code': 0,
            'msg': '', 
            'data': data
        })
    return JsonResponse({
        'code': 0,
        'msg': '', 
        'data': data
    })


def time_filter(request=None, field='should_repay_time'):
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
        # query_time = Q(should_repay_time__lte=end_time, should_repay_time__gte=start_time)  # 订单创建时间
    return query_time 


def update_time_filter(request=None):
    """"""
    time = request.GET.get('time')  
    start_time = end_time = None    
    # query_time = Q()                
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
    return start_time, end_time 


def _sort(query_set=None, request=None):
    """"""
    order_name = request.GET.get('order_name', '').strip()
    order_name = sort_dict.get(order_name)
    if query_set and request:
        order_way = request.GET.get('order_way', '').strip()
        if order_name and order_way:
            if 'asc' == order_way:
                return query_set.order_by(order_name)
            elif 'desc' == order_way:
                return query_set.order_by('-' + order_name)
        return query_set.order_by('-id')
    return []

class Receivables(DataProvider):
    """应收账单类"""

    def objects_filter(self, request):
        """"""
        query_time = time_filter(request)
        print 'query_time -> ', query_time

        query_platform = Q()
        user_platform = get_employee_platform(request)
        if len(user_platform) > 1:
            platform_param = request.GET.get('platform', '')
            if platform_param:
                query_platform = Q(repayment__platform = platform_param)
            else:
                query_platform = Q(repayment__platform__in = user_platform.values_list('name', flat = True))
        else:
            query_platform = Q(repayment__platform = user_platform[0].name)
        query_product = Q()
        product = request.GET.get('product', '')
        if product:
            query_product = Q(repayment__product = product)

        return InstallmentDetailInfo.objects.filter(query_time & Q(repay_status__in=['1', '2', '3', '7', '8', '9']) & query_platform & query_product)
    
    def search(self, query_set=None, request=None):
        """"""
        if query_set and request:
            search = request.GET.get('search', '').strip()
            if search:
                installments = query_set.filter(Q(repayment__order_number=search) | Q(repayment__user__name__icontains=search) | Q(repayment__user__id_no=search) | Q(repayment__user__phone_no=search))
                return installments
            return query_set
        return []

    def genrate_result(self, request):
        """"""
        _rows = self.objects_filter(request)
        # order_count = _rows.count()
        search_results = self.search(_rows, request)
        if search_results:
            order_count = search_results.count()
        else:
            order_count = 0
        sort_results = _sort(search_results, request)
        installments = self.pagination(sort_results, request)

        print 'orders count -> ', order_count
        print 'applies -> ', installments

        data = list()
        for im in installments:
            try:
                repayment = im.repayment
                user = repayment.user
                order = Apply.objects.filter(repayment=repayment).first()
                if not order:
                    continue
                strategy = u'{}个月'.format(repayment.installment_count)
                _strategy = Strategy2.objects.filter(strategy_id=repayment.strategy_id).first()
                if _strategy:
                    if _strategy.installment_type == 1:
                        strategy = u'{}个月'.format(_strategy.installment_count)
                    elif _strategy.installment_type == 2:
                        strategy = u'{}天'.format(_strategy.installment_count)
                data.append({
                    'id': order.id,
                    'order_number': repayment.order_number,
                    'username': user.name,
                    'id_no': user.id_no,
                    'should_repay_time': im.should_repay_time.strftime('%Y-%m-%d') if im.should_repay_time else '',
                    'amount': repayment.apply_amount if repayment.apply_amount else 0,
                    'strategy': strategy,
                    'loan_series': im.installment_number,
                    'salary': im.repay_fee if im.repay_fee else 0,
                    'overdue_days': im.overdue_days,
                    'overdue_salary': im.repay_overdue_interest if im.repay_overdue_interest else 0,
                    'overdue_fine': im.repay_penalty if im.repay_penalty else 0,
                    'break_fine': 0,
                    'receivable_amount': (im.should_repay_amount + im.repay_overdue_interest)
                })
            except:
                Log().info('')
                continue

        # url = request.build_absolute_uri()
        url = settings.DOMAIN + request.get_full_path()
        url = url.replace('receivables', 'down_receivables')
        return JsonResponse({
            'code': 0,
            'msg': '',
            'order_count': order_count,
            'url': url,
            'data': data
        })


@require_http_methods(['GET'])
def get_receivables(request):
    """"""
    return Receivables().genrate_result(request)


class PaidBills(DataProvider):
    """"""

    def objects_filter(self, request):
        """"""
        query_time = time_filter(request, 'real_repay_time')
        query_platform = Q()
        user_platform = get_employee_platform(request)
        if len(user_platform) > 1:
            platform_param = request.GET.get('platform', '')
            if platform_param:
                query_platform = Q(repayment__platform = platform_param)
            else:
                query_platform = Q(repayment__platform__in = user_platform.values_list('name', flat = True))
        else:
            query_platform = Q(repayment__platform = user_platform[0].name)
        query_product = Q()
        product = request.GET.get('product', '')
        if product:
            query_product = Q(repayment__product = product)

        return InstallmentDetailInfo.objects.filter(query_time & Q(repay_status__in=['3', '8', '9']) & query_platform & query_product)
    
    def search(self, query_set=None, request=None):                                                                          
        """"""    
        if query_set and request:  
            search = request.GET.get('search', '').strip()                                                                   
            if search:      
                installments = query_set.filter(Q(repayment__order_number=search) | Q(repayment__user__name__icontains=search) |                Q(repayment__user__id_no=search) | Q(repayment__user__phone_no=search))
                return installments
            return query_set
        return []

    def genrate_result(self, request):
        _rows = self.objects_filter(request)
        search_results = self.search(_rows,request)
        if search_results:
            order_count = search_results.count()
        else:
            order_count = 0
        sort_results = _sort(search_results, request)
        installments = self.pagination(sort_results, request)
        
        data = list()
        for im in installments:
            try:
                repayment = im.repayment
                user = repayment.user
                order = Apply.objects.filter(repayment=repayment).first()
                if not order:
                    continue
                
                strategy = u'{}个月'.format(repayment.installment_count)
                _strategy = Strategy2.objects.filter(strategy_id=repayment.strategy_id).first()
                if _strategy:            
                    if _strategy.installment_type == 1:
                        strategy = u'{}个月'.format(_strategy.installment_count)
                    elif _strategy.installment_type == 2:
                        strategy = u'{}天'.format(_strategy.installment_count)

                data.append({
                    'id': order.id,
                    'order_number': repayment.order_number,
                    'username': user.name,
                    'id_no': user.id_no,
                    'real_repay_time': im.real_repay_time.strftime('%Y-%m-%d') if im.real_repay_time else '',
                    'amount': repayment.apply_amount if repayment.apply_amount else 0,
                    'strategy': strategy,
                    'salary': im.repay_fee if im.repay_fee else 0,
                    'loan_series': im.installment_number,
                    'overdue_days': im.overdue_days,
                    'overdue_salary': im.repay_overdue_interest if im.repay_overdue_interest else 0,
                    'overdue_fine': im.repay_penalty if im.repay_penalty else 0,
                    'break_fine': 0,
                    'received_amount': im.real_repay_amount if im.real_repay_amount else 0
                })
            except:
                continue

        # url = request.build_absolute_uri()
        url = settings.DOMAIN + request.get_full_path()
        # p = re.search(r'(\?.*)', url)                                   
        # if p:                                                           
        #     url = ''                                                    
        url = url.replace('paid_in_bills', 'down_paid_in_bills')
        return JsonResponse({                                           
            'code': 0,                                                  
            'msg': '',                                                  
            'order_count': order_count,                                 
            'url': url,                                                 
            'data': data                                                
        })


@require_http_methods(['GET'])
def get_paid_in_bills(request):
    """"""
    return PaidBills().genrate_result(request)


class CheckRepayBills(DataProvider):
    """"""

    def objects_filter(self, request):
        """"""
        query_time = Q()
        start_time, end_time = update_time_filter(request)
        if start_time and end_time:
            query_time = Q(create_at__lte=end_time) & Q(create_at__gte=start_time)

        print 'query time -> ', query_time

        query_status = Q()
        _status = request.GET.get('order_status', '').strip()
        if 'waiting' == _status:
            query_status = Q(status=CheckApply.WAIT)
        elif 'success' == _status:
            query_status = Q(status=CheckApply.CHECK_SUCCESS)
        elif 'failed' == _status:
            query_status = Q(status=CheckApply.CHECK_FAILED)

        query_type = Q()
        _type = request.GET.get('order_type', '').strip()
        if 'alipay' == _type:
            query_type = Q(type=CheckApply.CHECK_ALIPAY)
        elif 'topublic' == _type:
            query_type = Q(type=CheckApply.CHECK_TOPUBLIC)

        query_platform = Q()
        user_platform = get_employee_platform(request)
        if len(user_platform) > 1:
            platform_param = request.GET.get('platform', '')
            if platform_param:
                query_platform = Q(platform = platform_param)
            else:
                query_platform = Q(platform__in = user_platform.values_list('name', flat = True))
        else:
            query_platform = Q(platform = user_platform[0].name)
        query_product = Q()
        product = request.GET.get('product', '')
        if product:
            query_product = Q(product = product)

        return CheckApply.objects.filter(query_time & query_status & query_type & query_platform & query_product)
    
    def search(self, query_set=None, request=None):                                                                          
        """"""    
        if query_set and request:  
            search = request.GET.get('search', '').strip()                                                                   
            if search:      
                user_id_query = Q()
                try:
                    search_id = int(search)
                    user_id_query = Q(repayment__user__id=search_id)
                except:
                    pass
                installments = query_set.filter(user_id_query | Q(repayment__user__name__icontains=search) |  Q(repayment__user__id_no=search) | Q(repayment__user__phone_no=search))
                return installments
            return query_set
        return []

    def genrate_result(self, request):
        """"""
        _rows = self.objects_filter(request)
        order_count = _rows.count()
        search_results = self.search(_rows, request)
        # order_count = search_results.count()
        sort_results = _sort(search_results, request)
        rows = self.pagination(sort_results, request)
        
        data = list()
        for al in rows:
            if al.status == CheckApply.WAIT:
                status_name = u'等待复核'
            elif al.status == CheckApply.CHECK_SUCCESS:
                status_name = u'复核成功'
            elif al.status == CheckApply.CHECK_FAILED:
                status_name = u'复核失败'
            else: 
                status_name = ''

            user = al.repayment.user
            staff = al.create_by
            data.append({
                'id': al.id,
                'user_id': user.id,
                'username': user.name,
                'repay_type': al.get_type_display(),
                'created_at': al.create_at.strftime('%Y-%m-%d') if al.create_at else '',
                'finish_time': al.finish_time.strftime('%Y-%m-%d') if al.finish_time else '',
                'staff': staff.username,
                'status': status_name
            })
        
        # url = request.build_absolute_uri()
        url = settings.DOMAIN + request.get_full_path()
        # p = re.search(r'(\?.*)', url)                                   
        # if p:
        #     url = ''                                                    
        url = url.replace('check_repay_bills', 'down_check_repay_bills')                                                           
        return JsonResponse({                                           
            'code': 0,
            'msg': '',                                                  
            'order_count': order_count,                                 
            'url': url,                                                 
            'data': data                                                
        })


@require_http_methods(['GET'])
def get_check_repay_bills(request):
    """"""
    return CheckRepayBills().genrate_result(request)


@require_http_methods(['GET'])
def get_check_repay_info(request, id=None):
    """"""
    order = CheckApply.objects.filter(pk=id).first()

    _money = str(round(order.money/100.0, 2))
    _money = _money[0:1] + 'xx' + _money[3:]
    data = {
        'id': order.id,
        'order_number': order.repayment.order_number,
        'name': order.repayment.user.name,
        'type': order.get_type_display(),
        'created_at': order.create_at.strftime('%Y-%m-%d') if order.create_at else '',
        'finish_time': order.finish_time.strftime('%Y-%m-%d') if order.finish_time else '',
        # 'amount': order.money / 100.0,
        'amount': _money if order.status not in ['k'] else order.money / 100.0,
        'employee': order.create_by.username,
        'pics': order.pic,
        'notes': order.notes
    }
    return JsonResponse({
        'code': 0,
        'msg': '',
        'data': data
    })


@require_http_methods(['GET'])
def down_tables(request, path=None):
    """"""
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S').replace('-', '').replace(' ', '').replace(':', '')
    wb = Workbook()
    ws = wb.create_sheet('orders', 0)

    xpath = ''

    if 'down_receivables' == path:
        _rows = Receivables().objects_filter(request)
        search_results = Receivables().search(_rows, request)
        sort_results = _sort(search_results, request)
        installments = _rows

 
        # rows = Receivables().genrate_result(request)
        ws.title = u'应收账单'
        ws.append([u"订单号", u"姓名", u"身份证号", u"应收日期", u"借款金额", u"借款期数", u"应收期数", u"应收服务费", u"逾期天数", u"应收逾期费用", u"应收逾期罚金", u"应收提前还款违约金", u"应收总额"])
        for im in installments:
            try:
                repayment = im.repayment
                user = repayment.user
                should_repay_time = ''
                if im.should_repay_time:
                    should_repay_time = im.should_repay_time.strftime('%Y-%m-%d')
                strategy = u'{}个月'.format(repayment.installment_count)
                # strategy = u'{}个月'.format(repayment.installment_count)
                _strategy = Strategy2.objects.filter(strategy_id=repayment.strategy_id).first()                                                   
                if _strategy:
                    if _strategy.installment_type == 1:
                        strategy = u'{}个月'.format(_strategy.installment_count)
                    elif _strategy.installment_type == 2:
                        strategy = u'{}天'.format(_strategy.installment_count)
                receivable_amount = (im.should_repay_amount + im.repay_overdue_interest) / 100.0
                ws.append([repayment.order_number, user.name, user.id_no, should_repay_time, repayment.apply_amount / 100.0, strategy, im.installment_number, im.repay_fee / 100.0, im.overdue_days, im.repay_overdue_interest / 100.0, im.repay_penalty / 100.0, 0, receivable_amount])
            except:
                continue

        xpath = 'receivables_{}.xlsx'.format(now)
        wb.save(xpath)
    elif 'down_paid_in_bills' == path:
        rows = PaidBills().objects_filter(request)
        ws.title = u'实收账单'
        ws.append([u"订单号", u"姓名", u"身份证号", u"实收日期", u"借款金额", u"借款期数", u"实收期数", u"实收服务费" ,u"逾期天数", u"实收逾期费用", u"实收逾期罚金", u"实收提前还款违约金", u"实收总额"])
        for im in rows:
            try:
                repayment = im.repayment
                user = repayment.user
                real_repay_time = ''
                if im.real_repay_time:
                    real_repay_time = im.real_repay_time.strftime('%Y-%m-%d')
                # strategy = u'{}个月'.format(repayment.installment_count)
                strategy = u'{}个月'.format(repayment.installment_count)
                _strategy = Strategy2.objects.filter(strategy_id=repayment.strategy_id).first()                                                   
                if _strategy:
                    if _strategy.installment_type == 1:
                        strategy = u'{}个月'.format(_strategy.installment_count)
                    elif _strategy.installment_type == 2:
                        strategy = u'{}天'.format(_strategy.installment_count)

                ws.append([repayment.order_number, user.name, user.id_no, real_repay_time, repayment.apply_amount / 100.0, strategy, im.installment_number, im.repay_fee / 100.0, im.overdue_days, im.repay_overdue_interest / 100.0, im.repay_penalty / 100.0, 0, im.real_repay_amount / 100.0])
            except:
                continue
        xpath = 'paidbills_{}.xlsx'.format(now)
        wb.save(xpath)
    elif 'down_check_repay_bills'  == path:
        rows = CheckRepayBills().objects_filter(request)
        ws.title = u'财务复核'
        ws.append([u"申请ID", u"用户ID", u"用户名", u"还款方式", u"提交时间",u"完成时间", u"提交人", u"处理状态"])
        for al in rows:
            try:
                if al.status == CheckApply.WAIT:
                    status_name = u'等待复核'
                elif al.status == CheckApply.CHECK_SUCCESS:
                    status_name = u'复核成功'
                elif al.status == CheckApply.CHECK_FAILED:
                    status_name = u'复核失败'
                else: 
                    status_name = ''

                user = al.repayment.user
                staff = al.create_by
                created_at = al.create_at.strftime('%Y-%m-%d') if al.create_at else ''
                finish_time = al.finish_time.strftime('%Y-%m-%d') if al.finish_time else ''

                ws.append([al.id, user.id, user.name, al.get_type_display(), created_at, finish_time, staff.username, status_name])
            except:
                continue
        xpath = 'check_repay_bills_{}.xlsx'.format(now)
        wb.save(xpath)
    else:
        pass
    
    response = StreamingHttpResponse(FileWrapper(open(xpath), 8192), content_type='application/vnd.ms-excel')
    response['Content-Length'] = os.path.getsize(xpath)                                                                                           
    response['Content-Disposition'] = 'attachment; filename={}'.format(xpath)
    try:
        os.system('rm {}'.format(xpath))
    except:
        pass
    return response                             
