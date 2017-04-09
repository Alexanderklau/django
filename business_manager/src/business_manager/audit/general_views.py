# -*- coding: utf-8 -*-
from django.conf import settings
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext, Template
from django.http import HttpResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
from django.core.servers.basehttp import FileWrapper

from datetime import datetime
from pyExcelerator import *
from business_manager.util.permission_decorator import page_permission
from business_manager.order.apply_models import Apply, CheckApply
from business_manager.employee.models import check_employee, get_employee
from business_manager.review.models import CollectionRecord
from business_manager.audit import data_views
from business_manager.audit.data_views import CheckApplyProvider
from business_manager.operation import data_views as data_views_operation
from business_manager.util.tkdate import *
from business_manager.collection.general_views import _update_related_repay_apply
from business_manager.operation.general_views import _update_related_collection_apply, get_realtime_repay_result,get_realtime_repay_result_not_bank_way
from business_manager.collection.models import *
from business_manager.python_common.log_client import CommonLog as Log
from business_manager.employee.models import Employee

from business_manager.python_common.dict import dict_addcount, dict_addmap, dict_addnumber
from business_manager.collection.strategy import Strategy
#from business_manager.order.models import BankCard, ContactInfo
from business_manager.review import message_client, bank_client, risk_client, redis_client
import json, traceback, os
from business_manager.collection.services import collection_extra_data

def get_table1_view(request):
    if request.method == 'GET':
        columns = data_views_operation.get_table1_columns()
        page= render_to_response('operation/table1.html', {"columns" : columns, "datatable" : []},
                                 context_instance=RequestContext(request))
        return page

def get_table2_view(request):
    if request.method == 'GET':
        columns = data_views_operation.get_table2_columns()
        page= render_to_response('operation/table2.html', {"columns" : columns, "datatable" : []},
                                 context_instance=RequestContext(request))
        return page

def get_table3_view(request):
    if request.method == 'GET':
        columns = data_views_operation.get_table3_columns()
        page= render_to_response('operation/table3.html', {"columns" : columns, "datatable" : []},
                                 context_instance=RequestContext(request))
        return page

@page_permission(check_employee)
def get_check_page_view(request):
    if request.method == 'GET':
        columns = data_views.get_check_columns()
        page= render_to_response('audit/check.html', {"columns" : columns, "datatable" : []},
                                 context_instance=RequestContext(request))
        return page

@page_permission(check_employee)
def get_receivables_page_view(request):
    if request.method == 'GET':
        columns = data_views.get_receivables_columns()
        page= render_to_response('audit/receivables.html', {"columns" : columns, "datatable" : []},
                                 context_instance=RequestContext(request))
        return page

@page_permission(check_employee)
def get_received_page_view(request):
    if request.method == 'GET':
        columns = data_views.get_received_columns()
        page= render_to_response('audit/received.html', {"columns" : columns, "datatable" : []},
                                 context_instance=RequestContext(request))
        return page

def hide_amount(amount):
    amount_str = str(round(amount/100.0, 2))
    return amount_str[0:1] + 'XX' + amount_str[3:]

@page_permission(check_employee)
def get_check_modal_view(request, apply_id):
    if request.method == 'GET':
        check_apply = CheckApply.objects.get(pk = apply_id)
        pics = check_apply.pic.split(";")
        invi_amount = hide_amount(check_apply.money)
        page= render_to_response('audit/check_modal.html', {"apply":check_apply, "pics":pics, "amount":invi_amount},
                                 context_instance=RequestContext(request))
        return page

#def get_installment_by_check_apply(check_apply):
#    pass

@csrf_exempt
def confirm_check(request):
    if request.method == 'POST':
        try:
            staff = Employee.objects.get(user = request.user)
            aid = request.POST.get('id') or request.POST.get("aid")
            amount = request.POST.get('check_amount') or request.POST.get("amount")
            notes = request.POST.get("notes")
            check_apply = CheckApply.objects.get(pk = aid)
            if not amount:
                return HttpResponse(json.dumps({'code': -1, "msg" : u"复核金额不能为空"}))
            check_apply_money = 0
            try:
                # check_apply_money = int(round(float(amount) * 100))
                check_apply_money = int(round(float(amount) * 1))
            except Exception, e:
                print e
                traceback.print_exc()
                Log().info("confirm_check failed %s" % (str(e)))
                return HttpResponse(json.dumps({'code': -1, "msg" : u"复核金额非法"}))
            print check_apply_money, check_apply.money
            if check_apply_money == check_apply.money:
                # if check_apply.repay_apply.type == Apply.REPAY_LOAN:
                #     check_apply.repay_apply.status = Apply.REPAY_SUCCESS
                #     check_apply.repay_apply.save()
                #     _update_related_collection_apply(check_apply.repay_apply)
                # else : #催收
                #     check_apply.repay_apply.status = Apply.COLLECTION_SUCCESS
                #     check_apply.repay_apply.save()
                #     _update_related_repay_apply(check_apply.repay_apply)
                #risk_client.repay_loan()
                #res = risk_client.repay_loan(check_apply.repayment.order_number, check_apply.installment, check_apply.money)
                REPAY_CHANNEL_TYPE_MAP = {
                    1:'realtime_repay' ,
                    3:'alipay_repay',
                    4:'topublic_repay',
                }
                repay_type = InstallmentDetailInfo.REPAY_TYPE_AUTO
                if check_apply.type == CheckApply.CHECK_ALIPAY:
                    repay_type = InstallmentDetailInfo.REPAY_TYPE_ALIPAY
                elif check_apply.type == CheckApply.CHECK_TOPUBLIC:
                    repay_type = InstallmentDetailInfo.REPAY_TYPE_PUB
                else:
                    Log().warn(u"unknown check apply type : %d. use default auto" % check_apply.type)
                print "here1"
                msg = get_realtime_repay_result_not_bank_way(check_apply, check_apply.repay_apply, check_apply.repay_type, amount,REPAY_CHANNEL_TYPE_MAP[repay_type],staff)
                print "here2"

                #res = risk_client.repay_loan(check_apply.repayment.order_number, check_apply.installment, repay_type)
                #if not res or res.result_code  != 0:
                #    Log().info(u"repay_loan to risk_server failed. order_number: %s, installment_number: %d"
                #                    % (check_apply.repayment.order_number, check_apply.installment))
                #    Log().info(u"res:%d" % res.result_code)
                #    return HttpResponse(json.dumps({"error" : "更新客户还款状态失败，请联系管理员"}))
                check_apply.status = CheckApply.CHECK_SUCCESS
                check_apply.finish_time = datetime.now()
                check_apply.save()
                #check_apply.repay_apply.save()
                print notes
                extra_data = collection_extra_data(check_apply.repay_apply)
                record = CollectionRecord(record_type=CollectionRecord.CHECK_NOTES, object_type=CollectionRecord.SELF, create_by = get_employee(request),
                        collection_note=u"财务备注:%s" % (notes), promised_repay_time=None, apply=check_apply.repay_apply, **extra_data)
                record.save()
                Log().info("confirm_check success %d" % check_apply_money)
                return HttpResponse(json.dumps({'code': 0, "msg" : u"金额匹配，复核成功"}))
            else:
                Log().info("confirm_check failed %d != %d" % (check_apply_money, check_apply.money))
                return HttpResponse(json.dumps({'code': -1, "msg" : u"金额不匹配"}))
        except Exception, e:
            print e
            traceback.print_exc()
            Log().info("confirm_check failed %s" % (str(e)))
            return HttpResponse(json.dumps({'code': -1, "msg" : u"确认复核失败"}))
    return HttpResponse(json.dumps({'code': -1, "msg" : u"post only"}))

@csrf_exempt
def back_check(request):
    if request.method == 'POST':
        try:
            aid = request.POST.get('id') or request.POST.get("aid")
            Log().info("check_back failed %s" % (aid))
            notes = request.POST.get("notes")
            if not notes:
                return HttpResponse(json.dumps({'code': -1, "msg" : u"打回必须填写原因"}))
            check_apply = CheckApply.objects.get(pk = aid)
            check_apply.status = CheckApply.CHECK_FAILED
            if check_apply.repay_apply.type == Apply.REPAY_LOAN:
                check_apply.repay_apply.status = Apply.CHECK_FAILED
                # _update_related_collection_apply(check_apply.repay_apply, Apply.PROCESSING)
                _update_related_collection_apply(check_apply.repay_apply, Apply.CHECK_FAILED)
                record = CollectionRecord(record_type=CollectionRecord.CHECK_BACK, object_type=CollectionRecord.SELF, create_by = get_employee(request),
                        collection_note=u"打回原因:%s" % (notes), promised_repay_time=None, apply=check_apply.repay_apply, check_apply=check_apply)
                record.save()
            else : #催收
                check_apply.repay_apply.status = Apply.CHECK_FAILED
                _update_related_repay_apply(check_apply.repay_apply, Apply.CHECK_FAILED)
                record = CollectionRecord(record_type=CollectionRecord.CHECK_BACK, object_type=CollectionRecord.SELF, create_by = get_employee(request),
                        collection_note=u"打回原因:%s" % (notes), promised_repay_time=None, apply=check_apply.repay_apply, check_apply=check_apply)
                record.save()
            check_apply.save()
            check_apply.repay_apply.save()
            Log().info("back_check success")
            return HttpResponse(json.dumps({"code" : 0, "msg": u"打回成功"}))
        except Exception, e:
            print e
            traceback.print_exc()
            Log().info("check_back failed %s" % (str(e)))
            return HttpResponse(json.dumps({'code': -1, "msg" : u"确认复核失败"}))
    return HttpResponse(json.dumps({'code': -1, "msg" : u"post only"}))

@csrf_exempt
def download_check_table(request):
    if request.method == 'GET':
        Log().info("download check_table")
        try :
            w = Workbook()
            ws = w.add_sheet('check_list-%s' % datetime.now().strftime("%y-%m-%d"))
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

            columns = CheckApplyProvider().get_columns()
            applys = CheckApplyProvider().object_filter(request)
            ws.write(0, 0, unicode("用户ID", 'utf-8'))
            ws.write(0, 1, unicode("用户名", 'utf-8'))
            ws.write(0, 2, unicode("还款方式", 'utf-8'))
            ws.write(0, 3, unicode("提交时间", 'utf-8'))
            ws.write(0, 4, unicode("复核时间", 'utf-8'))
            ws.write(0, 5, unicode("提交人", 'utf-8'))
            ws.write(0, 6, unicode("处理状态", 'utf-8'))
            ws.write(0, 7, unicode("金额", 'utf-8'))

            i = 1
            for c_apply in applys:
                ws.write(i, 0, c_apply.repayment.user.id)
                ws.write(i, 1, c_apply.repayment.user.name)
                ws.write(i, 2, c_apply.get_type_display())
                ws.write(i, 3, c_apply.create_at.strftime("%Y-%m-%d %H:%M:%S"))
                ws.write(i, 4, c_apply.finish_time.strftime("%Y-%m-%d %H:%M:%S") if c_apply.finish_time else "")
                ws.write(i, 5, c_apply.create_by.username)
                ws.write(i, 6, c_apply.get_status_display())
                ws.write(i, 7, round(c_apply.money/100.0, 2) if c_apply.status == CheckApply.CHECK_SUCCESS else "")
                i += 1

            w.save('s.xls')
        except Exception, e:
            print "excp", e
            traceback.print_exc()
            return HttpResponse(json.dumps({"error" : u"load failed"}))
        response = StreamingHttpResponse(FileWrapper(open('s.xls'), 8192), content_type='application/vnd.ms-excel')
        response['Content-Length'] = os.path.getsize("s.xls")
        response['Content-Disposition'] = 'attachment; filename=%s.xls' % 'check_list-%s' % datetime.now().strftime("%y-%m-%d")
        return response
    return HttpResponse(json.dumps({"error" : "get only"}))

@csrf_exempt
@page_permission(check_employee)
def download_receivable_table(request):
    if request.method == 'GET':
        timerange = request.GET.get("time")
        stime = get_today()
        etime = get_tomorrow()
        timerange = request.GET.get("time")
        if timerange == "today" :
            stime = get_today()
            etime = get_tomorrow()
        elif timerange == "twodays" :
            stime = get_yestoday()
            etime = get_tomorrow()
        elif timerange == "yestoday" :
            stime = get_yestoday()
            etime = get_today()
        elif timerange == "toweek" :
            stime = get_first_day_of_week()
            etime = get_tomorrow()
        elif timerange == "tomonth" :
            stime = get_first_day_of_month()
            etime = get_forword_month_day(start_day=get_first_day_of_month())
        else:
            stime = request.GET.get("stime") or stime
            etime = request.GET.get("etime") or etime

        if timerange == "all" :
            query_time = Q()
        else:
            query_time = Q(should_repay_time__lt = etime, should_repay_time__gte = stime)

        query_status = Q(repay_status__in=['3','8', '7','9','1'])
        installments = InstallmentDetailInfo.objects.filter(query_status & query_time)
        w = Workbook()
        ws = w.add_sheet('sheet1')

        ws.write(0, 0, u'订单号')
        ws.write(0, 1, u'姓名')
        ws.write(0, 2, u'身份证号')
        ws.write(0, 3, u'应收日期')
        ws.write(0, 4, u'借款金额')
        ws.write(0, 5, u'借款期数')
        ws.write(0, 6, u'应收期数')
        ws.write(0, 7, u'应收服务费')
        ws.write(0, 8, u'逾期天数')
        ws.write(0, 9, u'应收逾期费用')
        ws.write(0, 10, u'应收逾期罚金')
        ws.write(0, 11, u'应收提前还款违约金')
        ws.write(0, 12, u'应收总额')

        for i, installment in enumerate(installments):
            repayment = installment.repayment
            user = repayment.user
            apply = Apply.objects.filter(repayment = repayment)[0]
            _strategy = Strategy.objects.filter(strategy_id=apply.strategy_id)
            ws.write(i + 1, 0, apply.id)
            ws.write(i + 1, 1, user.name)
            ws.write(i + 1, 2, user.id_no)
            ws.write(i + 1, 3, installment.should_repay_time.strftime('%Y-%m-%d'))
            ws.write(i + 1, 4, repayment.apply_amount / 100.00)
            ws.write(i + 1, 5, _strategy[0].installment_count if apply.strategy_id!=0 and _strategy else 1)
            ws.write(i + 1, 6, installment.installment_number)
            ws.write(i + 1, 7, installment.repay_fee / 100.00)
            ws.write(i + 1, 8, installment.overdue_days)
            ws.write(i + 1, 9, installment.repay_overdue_interest / 100.00)
            ws.write(i + 1, 10, installment.repay_penalty / 100.00 if installment.repay_penalty else 0)
            ws.write(i + 1, 11, 0)
            ws.write(i + 1, 12, (installment.repay_fee + installment.repay_overdue) / 100.00)
        w.save('repay.xls')
        response = StreamingHttpResponse(FileWrapper(open('repay.xls')), content_type = 'application/vnd.ms-excel')
        response['Content-Length'] = os.path.getsize('repay.xls')
        response['Content-Disposition'] = 'attachment; filename=repay.xls'
        return response

@csrf_exempt
@page_permission(check_employee)
def download_received_table(request):
    if request.method == 'GET':
        timerange = request.GET.get("time")
        stime = get_today()
        etime = get_tomorrow()
        timerange = request.GET.get("time")
        if timerange == "today" :
            stime = get_today()
            etime = get_tomorrow()
        elif timerange == "twodays" :
            stime = get_yestoday()
            etime = get_tomorrow()
        elif timerange == "yestoday" :
            stime = get_yestoday()
            etime = get_today()
        elif timerange == "toweek" :
            stime = get_first_day_of_week()
            etime = get_tomorrow()
        elif timerange == "tomonth" :
            stime = get_first_day_of_month()
            etime = get_forword_month_day(start_day=get_first_day_of_month())
        else:
            stime = request.GET.get("stime") or stime
            etime = request.GET.get("etime") or etime

        if timerange == "all" :
            query_time = Q()
        else:
            query_time = Q(should_repay_time__lt = etime, should_repay_time__gte = stime)

        query_status = Q(repay_status__in=['3','8', '9'])
        installments = InstallmentDetailInfo.objects.filter(query_status & query_time)
        w = Workbook()
        ws = w.add_sheet('sheet1')

        ws.write(0, 0, u'订单号')
        ws.write(0, 1, u'姓名')
        ws.write(0, 2, u'身份证号')
        ws.write(0, 3, u'实收日期')
        ws.write(0, 4, u'借款金额')
        ws.write(0, 5, u'借款期数')
        ws.write(0, 6, u'实收期数')
        ws.write(0, 7, u'实收服务费')
        ws.write(0, 8, u'逾期天数')
        ws.write(0, 9, u'实收逾期费用')
        ws.write(0, 10, u'实收逾期罚金')
        ws.write(0, 11, u'实收提前还款违约金')
        ws.write(0, 12, u'实收总额')

        for i, installment in enumerate(installments):
            repayment = installment.repayment
            user = repayment.user
            apply = Apply.objects.filter(repayment = repayment)[0]
            ws.write(i + 1, 0, apply.id)
            ws.write(i + 1, 1, user.name)
            ws.write(i + 1, 2, user.id_no)
            ws.write(i + 1, 3, installment.real_repay_time.strftime('%Y-%m-%d'))
            ws.write(i + 1, 4, repayment.apply_amount / 100.00)
            ws.write(i + 1, 5, Strategy.objects.get(strategy_id=apply.strategy_id).installment_count if apply.strategy_id!=0 else 1)
            ws.write(i + 1, 6, installment.installment_number)
            ws.write(i + 1, 7, installment.repay_fee / 100.00)
            ws.write(i + 1, 8, installment.overdue_days)
            ws.write(i + 1, 9, installment.repay_overdue_interest / 100.00)
            ws.write(i + 1, 10, installment.repay_penalty / 100.00 if installment.repay_penalty else 0)
            ws.write(i + 1, 11, 0)
            ws.write(i + 1, 12, installment.real_repay_amount / 100.00)
        w.save('repayed.xls')
        response = StreamingHttpResponse(FileWrapper(open('repayed.xls')), content_type = 'application/vnd.ms-excel')
        response['Content-Length'] = os.path.getsize('repayed.xls')
        response['Content-Disposition'] = 'attachment; filename=repayed.xls'
        return response
