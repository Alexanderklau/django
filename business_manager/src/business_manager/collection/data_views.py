# -*- coding: utf-8 -*-
import json
from django.db.models import Q
from business_manager.order.apply_models import Apply
from business_manager.order.models import Chsi, CheckStatus, Profile
from business_manager.review.models import Review
from business_manager.util.tkdate import *
from business_manager.util.data_provider import DataProvider
from business_manager.python_common.log_client import CommonLog as Log
from business_manager.util.permission_decorator import page_permission
from business_manager.employee.models import check_employee
from django.http import HttpResponse, StreamingHttpResponse
from business_manager.review.models import *
from business_manager.collection.models import *
from datetime import datetime
# from .src.util.tkdate import get_today, get_tomorrow, get_yestoday, get_first_day_of_week, get_first_day_of_month
from ..util.tkdate import get_today,get_first_day_of_month,get_tomorrow,get_yestoday

# from business_manager.operation.general_views import fill_repay_modal_data

STATUS_DISPLAY_DIC = {
    Apply.WAIT: u"待分配",
    Apply.PROCESSING: u"未受理",
    Apply.COLLECTION: u"已受理",
    Apply.COLLECTION_SUCCESS: u'催收完成',
    Apply.REPAY_SUCCESS: u'扣款成功',
    Apply.PARTIAL_SUCCESS: u'部分成功',
}


class AllCollectionDataProvider(DataProvider):
    """
        所有催收
    """
    def object_filter(self, request):
        """
            time status 两个选择维度
        """
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
            etime = get_tomorrow()
        else:
            stime = request.GET.get("stime")
            etime = request.GET.get("etime")

        if timerange == "all" :
            query_time = Q()
            stime = None
            etime = None
        else:
            query_time = Q(create_at__lte = etime, create_at__gte = stime)

        self.start_time = stime
        self.end_time = etime
        print query_time
        apply_type =request.GET.get("type")
        query_type = None
        if apply_type == "m0" :
            query_type = Q(type='a')
        elif apply_type == "m1" :
            query_type = Q(type='b')
        elif apply_type == "m2" :
            query_type = Q(type='c')
        elif apply_type == "m3" :
            query_type = Q(type='d')
        elif apply_type == "m4" :
            query_type = Q(type__in=['e', 'h', 'g'])
        else :
            query_type = Q(type__in=['a', 'b', 'c', 'd', 'e', 'h', 'g'])

        apply_status = request.GET.get("status")
        self.apply_status = apply_status
        query_status = None
        if apply_status == "waiting":
            query_status = Q(status__in=["0", 's1'])
        elif apply_status == "processing":
            query_status = Q(status__in=["i", 's1'])
        elif apply_status == "collection":
            query_status = Q(status__in=["ci", "c", "d", 's3'])
        elif apply_status == "wait_check":
            query_status = Q(status = "k")
        elif apply_status == "check_failed":
            query_status = Q(status = "t")
        elif apply_status == "done":
            query_status = Q(status = "8") | Q(status = "9")
            if timerange == "all" :
                query_time = Q(real_repay_time__isnull=False)
            else:
                query_time = Q(real_repay_time__lte = etime, real_repay_time__gte = stime)

        elif apply_status == "repay_success":
            query_status = Q()
            if timerange == "all" :
                # query_time = Q(real_repay_time__isnull=False)
                query_time = Q(real_repay_time__isnull=False)
            else:
                # query_time = Q(real_repay_time__lte = etime, real_repay_time__gte = stime)
                query_time = Q(repayment__installmentdetailinfo__real_repay_time__lte = etime, repayment__installmentdetailinfo__real_repay_time__gte = stime)


        else:
            query_status = Q()

        channel = request.GET.get('channel')
        if channel == "all":
            query_channel = Q()
        else:
            query_channel = Q(create_by__channel=channel)

        overdue_days = request.GET.get("overdue_days")
        if overdue_days:
            start, end = overdue_days.split(",")
            try:
                start = int(start)
            except:
                start = -1
            try:
                end = int(end)
            except:
                end = -1
            query_start = Q(overdue_days__gte=start)if int(start) > 0 else Q()
            query_end = Q(overdue_days__lte=end)if int(end) > 0 else Q()
            query_overdue_days = query_start & query_end

        else:
            query_overdue_days = Q()

        employee_info = request.GET.get('employee')
        if employee_info == 'all' or not employee_info:
            employee_apply = None
            query_employee = Q()
        else:
            employee_id = employee_info[9:]
            employee = Employee.objects.filter(id=employee_id).first()
            if employee:
                query_employee = Q(employee=employee)
            else:
                query_employee = Q()

        # 期款金额筛选
        payment_info = request.GET.get('payment_range')
        print '------', payment_info
        if payment_info:
            payment_min, payment_max = payment_info.split(',')
            try:
                payment_min = int(payment_min)
                payment_max = int(payment_max)
            except:
                payment_min = -1
                payment_max = -1
            payment_start = Q(rest_repay_money__gte=payment_min) if payment_min > 0 else Q()
            payment_end = Q(rest_repay_money__lte=payment_max) if payment_max > 0 else Q()
            query_payment = payment_start & payment_end
        else:
            query_payment = Q()

        #print query_status, ",", query_type, ",", query_time
        print query_time
        print query_type
        print query_status
        print query_channel
        print query_overdue_days
        print query_employee
        apply_list = Apply.objects.filter(query_time & query_type & query_status & query_channel
                                          & query_overdue_days & query_employee & query_payment)
        if apply_status == "repay_success":
            apply_list = apply_list.values('repayment').annotate(c=Count('repayment'))
        print "apply"
        print apply_list.count()
        return apply_list

    def get_columns(self):
        #return [u"ID", u"用户名", u"应还日期", u"贷款方式", u"贷款金额", u"应还金额",  u"催收人", u"操作"]
        # return [u"ID", u"用户id", u"用户名", u"客户类型", u"应还日期", u"逾期天数", u"贷款金额", u"催收人", u"处理状态", u"操作"]
        # return [u"ID", u"工单号", u"用户名", u"进件日期", u"期款",  u"承诺还款时间", u"逾期天数", u"贷款金额", u"贷款渠道", u"催收人", u"催记时间", u"处理状态", u"操作"]
        return [u"ID", u"工单号", u"用户名", u"进件日期", u"期款",  u"承诺还款时间", u"逾期天数", u"贷款金额", u"贷款渠道", u"催收人", u"处理状态", u"操作"]
        #return [u"工单号", u"用户名", u"进件日期", u"期款",  u"承诺还款时间", u"逾期天数", u"贷款金额", u"贷款渠道", u"催收人", u"处理状态", u"操作"]

    def get_query(self):
        # return ["repayment__order_number__iexact", "create_by__id__iexact", "create_by__name__icontains", "create_by__phone_no__iexact", "repayment__order_number__iexact", "repayment__bank_card__card_number__iexact", "create_by__contactinfo__phone_no"]
        return ["repayment__order_number__iexact", "create_by__id__iexact", "create_by__name__icontains", "create_by__phone_no__iexact", "repayment__order_number__iexact", "repayment__bank_card__card_number__iexact"]
        # return ["id__iexact", "create_by__id__iexact", "create_by__name__icontains", "create_by__phone_no__iexact", "repayment__order_number__iexact"]

    def fill_data(self, query_set, data=None):
        data_set = []
        today = datetime.combine(data.today(), datetime.max.time())
        for result in query_set.values():
            apply = Apply.objects.get(pk = result["id"])
            user = apply.create_by
            #status_url = u"<a class='view_review' name='%d' href='#'>查看</a> <a class='dispatch_collection' name='%d' href='#'>分配</a>" % (apply.id, apply.id)
            #operation_url = u"<a class='view_review' name='%d' href='#'>查看</a> <a class='dispatch_collection' name='%d' href='#'>分配</a>" % (apply.id, apply.id)
            operation_url = u"<a class='do_collection' name='%s' href='#'>催收</a>" % apply.id
            chsi = Chsi.objects.filter(user=user)
            try:
                profile = Profile.objects.get(owner=user)
            except Profile.DoesNotExist:
                profile = None
            #profile = Profile.objects.get(owner=user)
            check = CheckStatus.objects.filter(owner=user)
            review = CollectionRecord.objects.filter(apply=apply, record_type=CollectionRecord.DISPATCH).order_by("-id")
            dispatch_url = u"<a class='dispatch_collection' name='%d' href='#'>未分配</a>" % (apply.id)
            if len(review) >= 1:
                dispatch_url = u"<a class='dispatch_collection' name='%d' href='#'>%s</a>" % (apply.id, review[0].create_by.username)
            installments = InstallmentDetailInfo.objects.filter(repayment=apply.repayment, installment_number=apply.money + 1)
            print 'get installmet\n'
            print installments
            if len(installments) == 1:
                installment = installments[0]
            else:
                continue
            #print installment
            repay_day = installment.should_repay_time if installment else ""
            coll_record = CollectionRecord.objects.filter(apply=apply).order_by("-id").first()
            promised_repay_time = coll_record.promised_repay_time.strftime("%Y-%m-%d") if coll_record and coll_record.promised_repay_time else ""
            channel = apply.create_by.channel

            pay_done = (installment.repay_status == RepaymentInfo.DONE) or (installment.repay_status == RepaymentInfo.OVERDUE_DONE)
            # overdu_days = apply.repayment.overdue_days
            # print 'aaaaaaaaaa'
            # print InstallmentDetailInfo.objects.filter(repayment=apply.repayment, overdue_days__gte=0).values_list('overdue_days')
            overdu_days = max([
                od[0] for od in InstallmentDetailInfo.objects.filter(repayment=apply.repayment, overdue_days__gt=0).values_list('overdue_days')])

            # rest_repay_money = fill_repay_modal_data(apply)["rest_repay_money"] / 100.0
            # rest_repay_money = installment.should_repay_amount / 100.0
            # if installment.repay_status in [3, 8]:
                # rest_repay_money = installment.real_repay_amount / 100.0

            all_ins = InstallmentDetailInfo.objects.filter(repayment=apply.repayment)
            rest_repay_money = sum([ins.should_repay_amount for ins in all_ins if ins.repay_status == 2]) / 100.0
            if not InstallmentDetailInfo.objects.filter(repayment=apply.repayment, repay_status=2):
                if InstallmentDetailInfo.objects.filter(repayment=apply.repayment, repay_status__in=[3, 8]):
                    print "real_repay_amount"
                    rest_repay_money = sum([ins.real_repay_amount for ins in all_ins if ins.repay_status in [3, 8]]) / 100.0


            #overdu_days = (today - repay_day).days if repay_day and not pay_done else 0
            # if pay_done and installment:
                # try:
                    # overdu_days = (datetime.combine(installment.real_repay_time, datetime.min.time()) - datetime.combine(installment.should_repay_time, datetime.min.time())).days
                # except Exception, e:
                    # overdu_days = 0
            data = [apply.id,
                    # user.id,
                    apply.repayment.order_number,
                    user.name,
                    # profile.get_job_display() if profile != None else "profile 不存在",
                    # profile.get_job_display() if profile != None else "未填写",
                    # repay_day.strftime("%Y-%m-%d"),
                    apply.create_at.strftime("%Y-%m-%d"),
                    rest_repay_money,
                    promised_repay_time,
                    overdu_days,
                    apply.repayment.apply_amount/100.0,
                    channel,
                    dispatch_url,
                    apply.get_status_display(),
                    operation_url]
            #print '90 ' * 100
            #print apply.type
            #print apply.status
            # if apply.type in ['a', 'b', 'c', 'd', 'e'] and apply.status in ['0', 0]:
                # data[8] = "等待催收"

            data_set.append(data)
        return data_set

class MyCollectionDataProvider(DataProvider):
    def object_filter(self, request):
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
            etime = get_tomorrow()
        else:
            stime = request.GET.get("stime")
            etime = request.GET.get("etime")

        if timerange == "all" :
            query_time = Q()
            stime = None
            etime = None
        else:
            query_time = Q(create_at__lte = etime, create_at__gte = stime)

        self.start_time = stime
        self.end_time = etime
        apply_type =request.GET.get("type")
        query_type = None
        if apply_type == "m0" :
            query_type = Q(type='a')
        elif apply_type == "m1" :
            query_type = Q(type='b')
        elif apply_type == "m2" :
            query_type = Q(type='c')
        elif apply_type == "m3" :
            query_type = Q(type='d')
        elif apply_type == "m4" :
            query_type = Q(type__in=['e', 'h', 'g'])
        else :
            query_type = Q(type__in=['a', 'b', 'c', 'd', 'e', 'h', 'g'])

        apply_status = request.GET.get("status")
        self.apply_status = apply_status
        query_status = None
        if apply_status == "waiting":
            query_status = Q(status__in=["0", 's1'])
        elif apply_status == "processing":
            # query_status = Q(status = "i") | Q(status = "c") | Q(status = "d")
            query_status = Q(status__in=["i", 's1'])
        elif apply_status == "collection":
            query_status = Q(status__in=["ci", "c", "d", 's3'])
        elif apply_status == "wait_check":
            query_status = Q(status = "k")
        elif apply_status == "check_failed":
            query_status = Q(status = "t")
        elif apply_status == "done":
            query_status = Q(status = "8") | Q(status = "9")
            if timerange == "all" :
                query_time = Q(real_repay_time__isnull=False)
            else:
                query_time = Q(real_repay_time__lte = etime, real_repay_time__gte = stime)

        elif apply_status == "repay_success":
            query_status = Q()
            if timerange == "all" :
                # query_time = Q(real_repay_time__isnull=False)
                query_time = Q(real_repay_time__isnull=False)
            else:
                # query_time = Q(real_repay_time__lte = etime, real_repay_time__gte = stime)
                query_time = Q(repayment__installmentdetailinfo__real_repay_time__lte = etime, repayment__installmentdetailinfo__real_repay_time__gte = stime)

        else:
            query_status = Q()

        channel = request.GET.get('channel')
        if channel == "all":
            query_channel = Q()
        else:
            query_channel = Q(create_by__channel=channel)

        overdue_days = request.GET.get("overdue_days")
        if overdue_days:
            start, end = overdue_days.split(",")
            try:
                start = int(start)
            except:
                start = -1
            try:
                end = int(end)
            except:
                end = -1

            query_start = Q(overdue_days__gte=start)if int(start) > 0 else Q()
            query_end = Q(overdue_days__lte=end)if int(end) > 0 else Q()
            query_overdue_days = query_start & query_end

        else:
            query_overdue_days = Q()

        #print query_status, ",", query_type, ",", query_time
        # owner_id =request.GET.get("owner_id")
        owner_id = request.user.id
        query_owner = Q (review__reviewer__user__id = owner_id)
        apply_list = Apply.objects.filter(query_owner & query_type & query_time & query_status & query_channel).distinct()
        #apply_list = Apply.objects.filter(query_time & query_type & query_status)
        return apply_list

    def get_columns(self):
        #return [u"ID", u"用户名", u"逾期类型", u"贷款方式", u"贷款金额", u"逾期金额", u"催收人", u"操作"]
        # return [u"ID", u"用户ID", u"用户名", u"客户类型", u"应还日期", u"逾期天数", u"承诺还款时间", u"贷款金额", u"处理状态", u"操作"] #u"应还本息合计"
        # return [u"ID", u"工单号", u"用户名", u"应还日期", u"逾期天数", u"承诺还款时间", u"贷款金额", u"处理状态", u"操作"] #u"应还本息合计"
        return [u"ID", u"工单号", u"用户名", u"进件日期", u"期款",  u"承诺还款时间", u"逾期天数", u"贷款金额", u"贷款渠道",u"处理状态", u"操作"]

    def get_query(self):
        return ["repayment__order_number__iexact", "create_by__id__iexact", "create_by__name__icontains", "create_by__phone_no__iexact", "repayment__order_number__iexact", "repayment__bank_card__card_number__iexact"]
        # return ["id__iexact", "create_by__id__iexact", "create_by__name__icontains", "create_by__phone_no__iexact", "repayment__order_number__iexact"]

    def fill_data(self, query_set):
        data_set = []
        today = datetime.combine(date.today(), datetime.max.time())
        for result in query_set.values():
            apply = Apply.objects.get(pk = result["id"])
            user = apply.create_by
            status_url = u"<a class='view_review' name='%d' href='#'>查看</a> <a class='dispatch_collection' name='%d' href='#'>分配</a>" % (apply.id, apply.id)
            # operation_url = u"<a class='view_review' name='%d' href='#'>查看</a> <a class='do_collection' name='%d' href='#'>催收</a>" % (apply.id, apply.id)
            operation_url = u"<a class='do_collection' name='%d' href='#'>催收</a>" % apply.id
            chsi = Chsi.objects.filter(user=user)
            profile = Profile.objects.filter(owner=user)
            check = CheckStatus.objects.filter(owner=user)
            review = Review.objects.filter(order=apply)

            installments = InstallmentDetailInfo.objects.filter(repayment=apply.repayment, installment_number=apply.money + 1)
            installment = None
            if len(installments) == 1:
                installment = installments[0]
            repay_day = installment.should_repay_time if installment else ""
            pay_done = (installment.repay_status == RepaymentInfo.DONE) or (installment.repay_status == RepaymentInfo.OVERDUE_DONE)
            #overdu_days = (today - repay_day).days if repay_day and not pay_done else 0
            overdu_days = apply.repayment.overdue_days
            # rest_repay_money = fill_repay_modal_data(apply)["rest_repay_money"] / 100.0

            all_ins = InstallmentDetailInfo.objects.filter(repayment=apply.repayment)
            rest_repay_money = sum([ins.should_repay_amount for ins in all_ins if ins.repay_status == 2]) / 100.0
            if not InstallmentDetailInfo.objects.filter(repayment=apply.repayment, repay_status=2):
                if InstallmentDetailInfo.objects.filter(repayment=apply.repayment, repay_status__in=[3, 8]):
                    print "real_repay_amount"
                    rest_repay_money = sum([ins.real_repay_amount for ins in installments])

            # if installment.repay_status in [3, 8]:
                # rest_repay_money = installment.real_repay_amount / 100.0

            if pay_done and installment:
                try:
                    overdu_days = (datetime.combine(installment.real_repay_time, datetime.min.time()) - datetime.combine(installment.should_repay_time, datetime.min.time())).days
                except Exception, e:
                    overdu_days = 0

            coll_record = CollectionRecord.objects.filter(apply=apply).order_by("-id").first()
            promised_repay_time = coll_record.promised_repay_time.strftime("%Y-%m-%d") if coll_record and coll_record.promised_repay_time else ""
            channel = apply.create_by.channel
            data = [apply.id,
                    apply.repayment.order_number,
                    user.name,
                    # user.profile.get_job_display(),
                    # repay_day.strftime("%Y-%m-%d"),
                    apply.create_at.strftime("%Y-%m-%d"),
                    rest_repay_money,
                    promised_repay_time,
                    overdu_days,
                    # apply.last_commit_at.strftime("%Y-%m-%d %H时") if apply.last_commit_at else "",
                    apply.repayment.apply_amount/100.0,
                    channel,
                    apply.get_status_display(),
                    operation_url]
            if apply.type in ['a', 'b', 'c', 'd', 'e'] and apply.status in ['0', 0]:
                data[7] = "等待催收"
            data_set.append(data)
        return data_set

def get_all_collection_datatable(request):
    return AllCollectionDataProvider().get_datatable(request)

def get_my_collection_datatable(request):
    return MyCollectionDataProvider().get_datatable(request)

def get_all_collection_columns():
    return AllCollectionDataProvider().get_columns()

def get_my_collection_columns():
    return MyCollectionDataProvider().get_columns()

def _get_record_data(request):
    apply_id = request.GET.get("apply_id")
    record_type = request.GET.get("record_type") or "all"
    query_type = None
    if record_type == "record" :
        query_type = Q(record_type=CollectionRecord.COLLECTION)
    elif record_type == "dispatch" :
        query_type = Q(record_type=CollectionRecord.DISPATCH)
    elif record_type == "message" :
        query_type = Q(record_type=CollectionRecord.MESSAGE)
    elif record_type == "repay" :
        query_type = Q(record_type=CollectionRecord.REPAY)
    else :
        query_type = Q()
    #print apply_id
    collection_apply = Apply.objects.get(id=apply_id)
    data_list = []
    for record in collection_apply.collectionrecord_set.filter(query_type).order_by("-id"):
        record_dict = dict()
        record_dict['id'] = record.id
        record_dict['record_type'] = record.get_record_type_display()
        record_dict['collector'] = record.create_by.username
        record_dict['add_time'] = record.create_at.strftime("%Y-%m-%d %H") if record.create_at else ""
        record_dict['promised_repay_time'] = record.promised_repay_time.strftime("%Y-%m-%d %H") if record.promised_repay_time else ""
        img_url = ''
        if record.check_apply:
            img_url = '<a href="_blank"> <img src="%s" /></a>' % record.check_apply.pic
        record_dict['notes'] = "%s -- %s %s" % (record.get_object_type_display(), record.collection_note, img_url)

        data_list.append(record_dict)
    output_data = {'data': data_list}
    return output_data

@page_permission(check_employee)
def get_collection_record_data(request):
    if request.method == 'GET':
        output_data = _get_record_data(request)
        return HttpResponse(json.dumps(output_data))
