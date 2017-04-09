# -*- coding: utf-8 -*-
import json
from django.db.models import Q
from business_manager.collection.models import InstallmentDetailInfo
from business_manager.order.apply_models import Apply
from business_manager.order.models import Chsi, CheckStatus, Profile
from business_manager.review.models import Review
from business_manager.config_center.models import *
from business_manager.util.tkdate import *
from business_manager.util.data_provider import DataProvider
from business_manager.python_common.log_client import CommonLog as Log
from business_manager.employee.models import *

from datetime import timedelta
from business_manager.review import mongo_client
import traceback

from datetime import date
from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied

class ReviewDataProvider(DataProvider):
    def object_filter(self, request):
        stime = get_today()
        etime = get_tomorrow()
        timerange =request.GET.get("time")
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
            etime = get_tomorrow()
        else:
            stime = request.GET.get("stime")
            etime = request.GET.get("etime")

        #print timerange, etime, stime
        time_filter = request.GET.get("time_filter")
        query_time = None
        if time_filter == "review":
            query_time = Q(finish_time__lt = etime, finish_time__gt = stime)
        else:
            query_time = Q(create_at__lt = etime, create_at__gt = stime)

        query_status = None
        status =request.GET.get("status")
        if status == 'all':
            query_status = Q()
        else:
            query_status = Q(status = status)

        using_workflow_id = WorkFlow.objects.filter(is_in_use=1)[0].id
        apply_workflow_query = Q(workflow_id=using_workflow_id)
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
        apply_list = Apply.objects.filter(query_time & query_status & apply_workflow_query & platform_query & product_query)
        return apply_list

    def get_columns(self):
        return [u"申请ID", u"用户ID", u"用户名", u"订单类型", u"提交时间", u"完成时间", u"审批人", u"金额", u"订单状态"]

    def get_query(self):
        return ["id__iexact", "create_by__id__iexact", "create_by__name__icontains", "create_by__phone_no__iexact", "create_by__id_no__iexact"]

    def fill_data(self, query_set):
        data_set = []
        for result in query_set.values():
            apply = Apply.objects.get(pk = result["id"])
            user = apply.create_by
            status_url = ""
            user_name = ""
            if apply.status != 'r':
                current_status = WorkStatus.objects.get(Q(workflow_id=apply.workflow_id) & Q(status_code=apply.status))
                show_name = current_status.other_name if current_status.other_name else current_status.name
            elif apply.status == 'r':
                show_name = '打回修改'
            if apply.status == '0' or apply.status == "i" or apply.status == 'w':   #等待审批
                if apply.type == '0' and apply.status == 'e':
                    status_url = u"<a class='view_review label label-warning' name='%d' href='#'>基本信息快照</a>" %(apply.id)
                elif apply.type == '0': #基本额度
                    status_url = u"<a class='view_review_1' name='%d' href='/static/SaasWeb/reviewReport.html?id=%d&editable=False'>%s</a>" %(apply.id, apply.id,show_name)
                elif apply.type == 's': #二次提现
                    status_url = u"<a class='view_second' name='%d' href='#'>%s</a>" %(apply.id, apply.get_status_display())
                else: #额度提升
                    status_url = u"<a class='view_promote' name='%d' href='#'>%s</a>" %(apply.id, apply.get_status_display())
                if apply.status == 'w': #基本信息审
                    status_url = u"<a class='view_review' name='%d' href='#'>等待数据</a>" % (apply.id)
                user_name = user.name
            else:
                user_name = user.name
                if apply.type == '0' and apply.status in ['r', 'e', 'b']:
                    if apply.status == 'e':
                        # status_url = u"<a class='view_review label label-warning' name='%d' href='#'>基本信息快照</a>" %(apply.id)
                        status_url = u"<a class='view_review ' name='%d' href='#'>基本信息快照</a>" %(apply.id)
                    elif apply.status == 'r':
                        # status_url = u"<a class='view_review label label-warning' name='%d' href='#'>打回修改</a>" %(apply.id)
                        status_url = u"<a class='view_review_1' name='%d' href='/static/SaasWeb/reviewReport.html?id=%d&editable=False'>打回修改</a>" %(apply.id, apply.id)
                    else:
                        status_url = u"<a class='view_review' name='%d' href='#'>机器拒绝</a>" %(apply.id)
                elif apply.type == '0': #基本信息审
                    status_url = u"<a class='view_review_1' name='%d' href='/static/SaasWeb/reviewReport.html?id=%d&editable=False'>%s</a>" %(apply.id, apply.id,show_name)
                elif apply.type == 's': #二次提现
                    status_url = u"<a class='view_second' name='%d' href='#'>%s</a>" %(apply.id, apply.get_status_display())
                else:   # 额度提升审批
                    status_url = u"<a class='view_promote' name='%d' href='#'>%s</a>" %(apply.id, apply.get_status_display())
            review = Review.objects.filter(order = apply).order_by("-id")
            data = [apply.id,
                    user.id,
                    user_name,
                    apply.get_type_display(),
                    apply.create_at.strftime("%Y-%m-%d %H:%M:%S") if apply.create_at else "",
                    apply.finish_time.strftime("%Y-%m-%d %H:%M:%S") if apply.finish_time else "",
                    review[0].reviewer.username if len(review) > 0 else "",
                    apply.amount/100.0,
                    status_url]
            data_set.append(data)
        return data_set


def _check_permission(request, status):
    workflow = WorkFlow.objects.get(is_in_use=1)
    workflow_query = Q(workflow=workflow)
    workstatus_query = Q(status_code=status)
    workstatus = WorkStatus.objects.filter(workflow_query & workstatus_query)[0]
    staff = Employee.objects.get(user = request.user)

    if workstatus.permission_scale == 0:
        if workstatus.permission_obj_id != staff.id:
            raise PermissionDenied
        pass
    elif workstatus.permission_scale == 1:
        employeegroup = EmployeeGroup.objects.get(id=workstatus.permission_obj_id)
        if employeegroup.id not in staff.group_list.all().values_list('id', flat=True):
            raise PermissionDenied
        pass
    elif not workstatus.permission_scale:
        pass


class MyReviewDataProvider(DataProvider):
    def object_filter(self, request):
        try:
            staff = Employee.objects.get(user = request.user)
            query_time = Q()

            query_status = None
            status =request.GET.get("status")
            owner = request.GET.get("owner")
            owner_id = request.GET.get("owner_id")
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

            using_workflow_id = WorkFlow.objects.filter(is_in_use=1)[0].id
            apply_workflow_query = Q(workflow_id=using_workflow_id)
            if status != 'all':
                apply_status_query = Q(status=status)
            else:
                apply_status_query = Q()

            mine_list = []
            if owner == "mine":
                query_owner = Q(review__reviewer__user__id = request.user.id) & Q(review__review_res=status)
                mine_list = Apply.objects.filter(Q(owner_type=0) & Q(owner_id=staff.id) & apply_status_query & platform_query & product_query).distinct()
                result_list = mine_list.distinct()
            elif owner == 'all':
                temp_list = Apply.objects.filter(apply_status_query & apply_workflow_query & platform_query & product_query).distinct()
                result_list = temp_list
            return result_list
        except Exception as e:
            traceback.print_exc()

    def get_columns(self):
        return [u"申请ID", u"用户ID", u"用户名", u"订单类型", u"渠道来源", u"提交时间", u"完成时间", u"审批人", u"订单状态"]

    def get_query(self):
        return ["id__iexact", "create_by__id__iexact", "create_by__name__icontains", "create_by__phone_no__iexact", "create_by__id_no__iexact"]

    def fill_data(self, query_set):
        data_set = []
        user_name = ''
        user_channel = ''
        for result in query_set.values():
            apply = Apply.objects.get(pk = result["id"])
            user = apply.create_by
            status_url = ""
            if apply.status != 'r':
                current_status = WorkStatus.objects.get(Q(workflow_id=apply.workflow_id) & Q(status_code=apply.status))
                show_name = current_status.other_name if current_status.other_name else current_status.name
            elif apply.status == 'r':
                show_name = '打回修改'
            if apply.status not in ['y', 'n']:
                if apply.type == '0': #基本信息审
                    status_url = u"<span class='review_manual'  style='cursor:pointer' name='%d'>%s</span>" %(apply.id, show_name)
                    #status_url = u"<a class='view_review_1' name='%d' href='/static/SaasWeb/reviewReport.html?id=%d&editable=True'>%s</a>" %(apply.id, apply.id,show_name)
                elif apply.type == 's': #二次提现
                    status_url = u"<a class='review_loan' name='%d' href='#'>二次提现申请</a>" % (apply.id)
                else:   # 额度提升审批
                    status_url = u"<a class='review_promote' name='%d' href='#'>额度提升审批</a>" % (apply.id)
                user_name = user.name
                user_channel = user.channel
            else:  #已经完成审批，点击查看状态
                user_name = user.name
                user_channel = user.channel
                if apply.type == '0' and apply.status in ['r', 'e', 'b']:
                    if apply.status == 'e':
                        status_url = u"<a class='view_review ' name='%d' href='#'>基本信息快照</a>" %(apply.id)
                    elif apply.status == 'r':
                        status_url = u"<span class='review_manual'  style='cursor:pointer' name='%d'>%s</span>" %(apply.id, show_name)
                    else:
                        status_url = u"<a class='view_review' name='%d' href='#'>机器拒绝</a>" %(apply.id)
                elif apply.type == '0': #基本信息审
                    status_url = u"<span class='review_manual'  style='cursor:pointer' name='%d'>%s</span>" %(apply.id, show_name)
                    #status_url = u"<a class='view_review_1' name='%d' href='/static/SaasWeb/reviewReport.html?id=%d&editable=True'>%s</a>" %(apply.id, apply.id,show_name)
                elif apply.type == 's': #二次提现
                    status_url = u"<a class='view_second' name='%d' href='#'>%s</a>" %(apply.id, apply.get_status_display())
                else:   # 额度提升审批
                    status_url = u"<a class='view_promote' name='%d' href='#'>%s</a>" %(apply.id, apply.get_status_display())
            review = Review.objects.filter(order=apply).order_by("-id")
            if apply.status != 'w':
                reviewer = ''
                if review and apply.status == '0':
                    if 1 == review[0].order.owner_type:
                        eg = EmployeeGroup.objects.get(id= int(json.loads(review[0].order.owner_id)[0]))
                        if eg:
                            reviewer = eg.group_name
                    else:
                        reviewer = review[0].reviewer.username
                elif apply.status != '0':
                    if apply.owner_type == 0:
                        reviewer = Employee.objects.get(id=apply.owner_id).username
                    elif apply.owner_type == 1:
                        owners_id = json.loads(apply.owner_id)
                        group_name_set = EmployeeGroup.objects.filter(id__in = owners_id).values_list('group_name', flat=True)
                        reviewer = ' ,'.join(group_name_set)
                data = [apply.id,
                    user.id,
                    user_name,
                    #chsi[0].school if len(chsi) > 0 else "",
                    apply.get_type_display(),
                    # user_channel,
                    'saas',
                    apply.create_at.strftime("%Y-%m-%d %H:%M:%S") if apply.create_at else "",
                    apply.finish_time.strftime("%Y-%m-%d %H:%M:%S") if apply.finish_time else "",
                    # review[0].reviewer.username if len(review) > 0 else "",
                    reviewer,
                    status_url]
                data_set.append(data)
        return data_set

def get_all_review_datatable(request):
    try:
        return ReviewDataProvider().get_datatable(request)
    except Exception as e:
        traceback.print_exc()

def get_my_review_datatable(request):
    try:
        return MyReviewDataProvider().get_datatable(request)
    except Exception as e:
        traceback.print_exc()

def get_all_review_columns():
    try:
        return ReviewDataProvider().get_columns()
    except Exception as e:
        traceback.print_exc()

def get_my_review_columns():
    try:
        return MyReviewDataProvider().get_columns()
    except Exception as e:
        traceback.print_exc()


