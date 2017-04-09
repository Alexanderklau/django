# -*- coding: utf-8 -*-

from django.db.models import Q
from business_manager.order.apply_models import Apply
from business_manager.order.models import *
from business_manager.util.tkdate import *
from business_manager.util.data_provider import DataProvider
from business_manager.python_common.log_client import CommonLog as Log
from business_manager.config_center.models import WorkFlow, WorkStatus
from django.http import HttpResponse
import json
import traceback
import sys

reload(sys)
sys.setdefaultencoding( "utf-8" )

class OrderDataProvider(DataProvider):
    def object_filter(self, request):
        stime = get_today()
        etime = get_tomorrow()
        timerange =request.GET.get("time")
        if timerange == "today" :
            stime = get_today()
            etime = get_tomorrow()
        elif timerange == "yestoday" :
            stime = get_yestoday()
            etime = get_today()
        elif timerange == "toweek" :
            stime = get_first_day_of_week()
            etime = get_tomorrow()
        elif timerange == "tomonth" :
            stime = get_first_day_of_month()
            etime = get_tomorrow()
        else:
            stime = request.GET.get("stime")
            etime = request.GET.get("etime")

        print stime, etime
        try:
            # order_list = Apply.objects.filter(Q(create_at__lt = etime, create_at__gt = stime))
            order_list = Apply.objects.filter(Q(type = '0'))
            return order_list
        except Exception,e:
            print 'filter failed:', e
            return None
        #print Apply.objects.filter(Q(create_at__lt = etime) and Q(create_at__gt = stime)).query
        #print 'filter result:', order_list
        #return order_list

    def get_columns(self):
        # return [u"订单ID", u"用户ID", u"用户来源", u"订单类型", u"创建时间", u"处理时间", u"订单状态"]
        return [u"订单ID", u"用户ID", u"创建时间", u"订单状态"]

    def get_query(self):
        return ["id__iexact", "create_by__name__icontains", "create_by__phone_no__icontains", "create_by__id_no__iexact"]

    def fill_data(self, query_set):
        data_set = []
        for result in query_set.values():
            apply = Apply.objects.get(pk = result["id"])
            user = apply.create_by
            chsi = Chsi.objects.filter(user=user)
            # status_url = u"<a class='view_review_1' name='%d' href=''>%s</a>" %(apply.id, apply.get_status_display())
            try:
                if apply.status != 'r':
                    current_status = WorkStatus.objects.get(Q(workflow_id=apply.workflow_id) & Q(status_code=apply.status))
                    show_name = current_status.other_name if current_status.other_name else current_status.name
                elif apply.status == 'r':
                    show_name = u'打回修改'
            except Exception as e:
                show_name = apply.get_status_display()

            print show_name
            status_url = u"<a class='view_review_1' name='%d' href='/static/SaasWeb/reviewReport.html?id=%d&editable=False'>%s</a>" %(apply.id, apply.id, show_name)
            data = [apply.id,
                    user.name,
                    apply.create_at.strftime("%Y-%m-%d %H:%M:%S") if apply.create_at else "",
                    status_url,
                    ]
            data_set.append(data)
        return data_set

def get_order_datatable(request):
    try:
        return OrderDataProvider().get_datatable(request)
    except Exception as e:
        traceback.print_exc()

def get_order_columns():
    try:
        return OrderDataProvider().get_columns()
    except Exception as e:
        traceback.print_exc()


class ApplyOrderDataProvider(DataProvider):
    def object_filter(self, request):
        stime = get_today()
        etime = get_tomorrow()
        timerange =request.GET.get("time")
        if timerange == "today" :
            stime = get_today()
            etime = get_tomorrow()
        elif timerange == "yestoday" :
            stime = get_yestoday()
            etime = get_today()
        elif timerange == "toweek" :
            stime = get_first_day_of_week()
            etime = get_tomorrow()
        elif timerange == "tomonth" :
            stime = get_first_day_of_month()
            etime = get_tomorrow()
        else:
            stime = request.GET.get("stime")
            etime = request.GET.get("etime")

        #print stime, etime
        order_list = Apply.objects.filter(Q(type = '0', create_at__lt = etime, create_at__gt = stime))
        #print Apply.objects.filter(Q(create_at__lt = etime) and Q(create_at__gt = stime)).query
        return order_list

    def get_columns(self):
        return [u"订单ID", u"用户ID", u"用户来源", u"订单类型", u"创建时间", u"处理时间", u"订单状态"]

    def get_query(self):
        return ["id__iexact", "create_by__name__icontains", "create_by__phone_no__icontains"]

    def fill_data(self, query_set):
        data_set = []
        for result in query_set.values():
            apply = Apply.objects.get(pk = result["id"])
            print "apply", apply
            if apply:
                user = apply.create_by
                chsi = Chsi.objects.filter(user=user)
                data = [apply.id,
                        user.name,
                        chsi[0].school if len(chsi) > 0 else "",
                        apply.get_type_display(),
                        apply.create_at.strftime("%Y-%m-%d %H:%M:%S") if apply.create_at else "",
                        apply.finish_time.strftime("%Y-%m-%d %H:%M:%S") if apply.finish_time else "",
                        apply.get_status_display()]
                data_set.append(data)
        return data_set

def get_apply_order_datatable(request):
    return ApplyOrderDataProvider().get_datatable(request)

def get_apply_order_columns():
    return ApplyOrderDataProvider().get_columns()

class PromotionOrderDataProvider(DataProvider):
    def object_filter(self, request):
        stime = get_today()
        etime = get_tomorrow()
        timerange =request.GET.get("time")
        if timerange == "today" :
            stime = get_today()
            etime = get_tomorrow()
        elif timerange == "yestoday" :
            stime = get_yestoday()
            etime = get_today()
        elif timerange == "toweek" :
            stime = get_first_day_of_week()
            etime = get_tomorrow()
        elif timerange == "tomonth" :
            stime = get_first_day_of_month()
            etime = get_tomorrow()
        else:
            stime = request.GET.get("stime")
            etime = request.GET.get("etime")

        #print stime, etime
        order_list = Apply.objects.filter(Q(type__lt = '9', type__gt = '0', create_at__lt = etime, create_at__gt = stime))
        #print Apply.objects.filter(Q(create_at__lt = etime) and Q(create_at__gt = stime)).query
        return order_list

    def get_columns(self):
        return [u"订单ID", u"用户ID", u"用户来源", u"订单类型", u"创建时间", u"处理时间", u"订单状态"]

    def get_query(self):
        return ["id__iexact", "create_by__name__icontains", "create_by__phone_no__icontains"]

    def fill_data(self, query_set):
        data_set = []
        for result in query_set.values():
            apply = Apply.objects.get(pk = result["id"])
            user = apply.create_by
            chsi = Chsi.objects.filter(user=user)
            data = [apply.id,
                    user.name,
                    chsi[0].school if len(chsi) > 0 else "",
                    apply.get_type_display(),
                    apply.create_at.strftime("%Y-%m-%d %H:%M:%S") if apply.create_at else "",
                    apply.finish_time.strftime("%Y-%m-%d %H:%M:%S") if apply.finish_time else "",
                    apply.get_status_display()]
            data_set.append(data)
        return data_set

def get_promotion_order_datatable(request):
    return PromotionOrderDataProvider().get_datatable(request)

def get_promotion_order_columns():
    return PromotionOrderDataProvider().get_columns()

class LoanOrderDataProvider(DataProvider):
    def object_filter(self, request):
        stime = get_today()
        etime = get_tomorrow()
        timerange =request.GET.get("time")
        if timerange == "today" :
            stime = get_today()
            etime = get_tomorrow()
        elif timerange == "yestoday" :
            stime = get_yestoday()
            etime = get_today()
        elif timerange == "toweek" :
            stime = get_first_day_of_week()
            etime = get_tomorrow()
        elif timerange == "tomonth" :
            stime = get_first_day_of_month()
            etime = get_tomorrow()
        else:
            stime = request.GET.get("stime")
            etime = request.GET.get("etime")

        #print stime, etime
        order_list = Apply.objects.filter(Q(type = 'l', create_at__lt = etime, create_at__gt = stime))
        #print Apply.objects.filter(Q(create_at__lt = etime) and Q(create_at__gt = stime)).query
        return order_list

    def get_columns(self):
        return [u"订单ID", u"用户ID", u"借贷金额", u"订单类型", u"创建时间", u"处理时间", u"订单状态"]

    def get_query(self):
        return ["id__iexact", "create_by__name__icontains", "create_by__phone_no__icontains", "create_by__id_no__iexact"]

    def fill_data(self, query_set):
        data_set = []
        for result in query_set.values():
            apply = Apply.objects.get(pk = result["id"])
            user = apply.create_by
            data = [apply.id,
                    user.name,
                    # "%d.%d" % (apply.money/100, apply.money%100),
                    # apply.get_type_display(),
                    apply.create_at.strftime("%Y-%m-%d %H:%M:%S") if apply.create_at else "",
                    # apply.finish_time.strftime("%Y-%m-%d %H:%M:%S") if apply.finish_time else "",
                    apply.get_status_display()]
            data_set.append(data)
        print '@@'*20
        print data_set
        return data_set

def get_loan_order_datatable(request):
    return LoanOrderDataProvider().get_datatable(request)

def get_loan_order_columns():
    return LoanOrderDataProvider().get_columns()

def _get_user_info_note_data(request):
    user_id = request.GET.get("user_id")
    user = User.objects.get(id = user_id)
    data_list = []
    for record in UserExtraInfoRecord.objects.filter(user=user):
        record_dict = dict()
        record_dict['add_time'] = record.create_at.strftime("%Y-%m-%d %H") if record.create_at else ""
        record_dict['add_staff'] = str(record.create_by.username)
        record_dict['notes'] = record.content

        data_list.append(record_dict)
    output_data = {'data': data_list}
    return output_data

def get_user_info_note_data(request):
    if request.method == 'GET':
        output_data = _get_user_info_note_data(request)
        return HttpResponse(json.dumps(output_data))
