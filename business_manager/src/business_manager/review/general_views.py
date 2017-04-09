# -*- coding: utf-8 -*-
from django.conf import settings
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext, Template, Context
from django.http import HttpResponse, StreamingHttpResponse, HttpResponseRedirect
from django.core.servers.basehttp import FileWrapper
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.views.decorators.csrf import csrf_exempt
from django.core.management import call_command
from django.db.models import Count
from django.views.decorators.clickjacking import xframe_options_exempt
import os
import json
import random
import base64
import redis
import traceback
import time
import md5
from pyExcelerator import *
import xlwt
from datetime import datetime
from business_manager.util.permission_decorator import page_permission
from business_manager.util.constant import *
from business_manager.employee.models import check_employee, is_review_manager
from business_manager.review import data_views
from business_manager.util.cron_functions import get_apply_from_install
from business_manager.review import data_query
from business_manager.review.models import Review, ReviewRecord, Label, review_status_t
from business_manager.employee.models import  Employee, Platform
#from business_manager.juxinli.models import *
from business_manager.order.apply_models import Apply, ExtraApply
from business_manager.order.models import BankCard, ContactInfo, Chsi, CheckStatus, IdCard, Profile, AddressBook, CallRecord, \
    User, Chsiauthinfo, SubChannel
from business_manager.strategy.models import Strategy2
from business_manager.collection.models import RepaymentInfo, InstallmentDetailInfo
from business_manager.python_common.log_client import CommonLog as Log
from business_manager.python_common.dict import dict_addcount, dict_addmap
from business_manager.util.tkdate import *
from business_manager.config_center.models import *
from Crypto.Cipher import AES
from business_manager.review import mongo_client, user_center_client, redis_client, data_report_client, risk_client
from django.core import serializers
from threading import Timer
#from business_manager.review import push_client_object
from business_manager.order_management_server.utils import send_message_weixin
import requests

from business_manager.operation.general_views import try_to_get_repay_bank_amount

def value_to_key(data):
    modules = data['logic_rsp']['module_set']
    for module in modules:
        for field in module['field_set']:
            if field['string_json']:
                dic = json.loads(field['string_json'])
                string_user_value = field['string_user_value']
                new_string_user_value = {str(v): k for k, v in dic.items()}.get(string_user_value, string_user_value)
                field['string_user_value'] = new_string_user_value
    return

# @page_permission(check_employee)
# def get_rst(request):
    # if request.method == 'GET':
        # columns = data_views.get_my_review_columns()
        # # columns = data_views.get_rt_order_columns()
        # start_review = redis_client.get("reviewer:%s" % request.user.id)
        # url = 'http://121.40.202.86:8090/get_submitted_profile?search_key=13928449141&product=test_product&platform=dev'
        # data = requests.get(url).json()
        # value_to_key(data)

        # dic = {
            # "string_name": "贷款策略",
            # "string_description": "策略说明",
            # "int32_amount": "贷款金额",
            # "string_reason": "贷款用途",
            # "string_address": "账单地址",

        # }
        # strategy_info = data['logic_rsp']['strategy_info']
        # data['logic_rsp']['strategy_info'] = { dic.get(k, k): v for k, v in strategy_info.items() if k not in ['int32_strategy_id']}
        # profile_data = data['logic_rsp']['module_set'][3]['field_set']
        # data['logic_rsp']['module_set'][3]['images'] = profile_data[0]['string_user_value'].split('|')
        # contact_data = data['logic_rsp']['module_set'][4]['field_set']
        # data['logic_rsp']['module_set'][4]['datas'] = [contact_str.split('_')for contact_str in contact_data[0]['string_user_value'].split('|')]

        # apply_id = 29
        # apply_info = Apply.objects.get(pk=apply_id)
        # if apply_info.status == 'b':
            # review_dict = _read_snapshot_apply(request, apply_id)
        # else:
            # review_dict = _get_info_by_apply(request, apply_id)
        # labels = _get_review_label()
        # review_dict.update(labels)
        # if review_dict['check_status'].auto_check_status in (2, 3, 4, -11,):
            # review_dict['check_status'].auto_check_status = 0

        # report_dic = get_report_page(request, apply_id)
        # review_dict.update(report_dic)


        # data.update(review_dict)

        # # review_contact_dict = _get_interface_data(request, apply_info.create_by)
        # # # user = User.objects.get(pk=apply_info.create_by.id)
        # # apply_dict = _get_review_info(request, apply_info)
        # # if not apply_dict["reviews"]:
            # # last_apply = _get_last_basic_apply(apply_info.create_by)
            # # apply_dict = _get_review_info(request, last_apply)

        # # review_contact_dict.update(apply_dict)

        # # data.update(review_contact_dict)
        # page = render_to_response(
            # 'review/modal.html',
            # data,
            # context_instance=RequestContext(request))
        # return page



def _get_members_detail_info():
    record_table = mongo_client['dispatch']['daily_records']
    day = datetime.now().date()
    day_str = day.strftime('%Y%m%d')
    yesterday = day - timedelta(days=1)
    yesterday_str = yesterday.strftime('%Y%m%d')
    today_data = record_table.find_one({"day": day_str}, {"_id": 0})
    yesterday_data = record_table.find_one({"day": yesterday_str}, {"_id": 0})
    reviewer_lists = [i['reviewer_id'] for i in today_data['data']]
    staff_lists = Employee.objects.filter(user__id__in=reviewer_lists).values('user__id', 'username')
    members_dict = {int(i['user__id']): i['username'] for i in staff_lists}
    if today_data:
        pass_mount = ((int(i["reviewer_id"]), i["pass_mount"], i['today_total_tasks']) for i in today_data['data'])
        pass_rate = dict(map(lambda (x, y, z): (x, round(y / float(z), 2)) if z else (x, 0), pass_mount))
        second_loan_num = {
        int(i["reviewer_id"]): i["second_pass_mount"] + i['second_reject_mount'] + i["second_back_mount"]
        for i in today_data['data']}
        overdue_apply_num = {int(i["reviewer_id"]): i['overdue_apply_num']
                             for i in today_data['data']}
    else:
        pass_rate = {k: 0 for k, v in members_dict.items()}
        second_loan_num = {k: 0 for k, v in members_dict.items()}
        overdue_apply_num = {k: 0 for k, v in members_dict.items()}
    if yesterday_data:
        second_loan_num_yesterday = {
        i["reviewer_id"]: i["second_pass_mount"] + i['second_reject_mount'] + i["second_back_mount"]
        for i in yesterday_data['data']}
        yesterday_pass_mount = ((int(i["reviewer_id"]), i["pass_mount"], i['today_total_tasks']) for i in
                                yesterday_data['data'])
        yesterday_pass_rate = dict(
            map(lambda (x, y, z): (x, round(y / float(z), 2)) if z else (x, 0), yesterday_pass_mount))
        if 'overdue_apply_num' in yesterday_data['data']:
            overdue_apply_num_yesterday = {int(i["reviewer_id"]): i['overdue_apply_num']
                                           for i in yesterday_data['data']}

        else:
            overdue_apply_num_yesterday = {k: 0 for k, v in members_dict.items()}
    else:
        yesterday_pass_rate = {k: 0 for k, v in members_dict.items()}
        second_loan_num_yesterday = {k: 0 for k, v in members_dict.items()}
        overdue_apply_num_yesterday = {k: 0 for k, v in members_dict.items()}

    members_detail_info = {k: {"member_name": v} for k, v in members_dict.items()}
    # 每个审批专员的通过率
    for k, v in pass_rate.items():
        members_detail_info[k].update({"pass_rate": v * 100})
    for k, v in yesterday_pass_rate.items():
        members_detail_info[k].update({"pass_rate_yesterday": v * 100})
    for k, v in second_loan_num.items():
        members_detail_info[k].update({"second_loan_num": v})
    for k, v in second_loan_num_yesterday.items():
        members_detail_info[int(k)].update({"second_loan_num_yesterday": v})
    for k, v in overdue_apply_num.items():
        members_detail_info[int(k)].update({"overdue_apply_num": v})
    for k, v in overdue_apply_num_yesterday.items():
        members_detail_info[int(k)].update({"overdue_apply_num_yesterday": v})
    return members_detail_info


def get_review_employee(request):
    """
    审批专员信息
    """
    employee_template_str = '''
        {%for member in members%}
                <li class="list-group-item "><span class="icon-svg icon-svg-xl svg-icon_small_check_staff"></span>
                <a data-id="{{member.id}}" > {{member.name}}</a></li>
        {%endfor%}
    '''
    # page = int(request.GET.get("page", 1))
    template = Template(employee_template_str)

    members_detail_info = _get_members_detail_info()
    members = [{"id": _m, "name": members_detail_info[_m]["member_name"]} for _m in members_detail_info]

    context = Context(dict(members=members))

    # for member in members:
    #     mid = member["id"]
    #     members_detail_info[mid] = dict(
    #         member_name=mid,
    #         done_rate=98.8,
    #         pass_rate=97.7,
    #         second_loan_num=100,
    #         second_loan_num_yesterday=20,
    #         overdue_apply_num=200,
    #         overdue_apply_num_yesterday=40
    #     )

    data = {
        "employee": template.render(context),
        "employee_detail_info": members_detail_info,
    }
    if int(request.GET.get("page", 1)) >= 4:
        data = {}

    return HttpResponse(json.dumps(data))


@page_permission(check_employee)
def change_employee_status(request):
    try:
        status = request.GET.get("status")
        if status == 'online':
            r = redis_client.delete("reviewer:%s" % request.user.id)
        else:
            # r = redis_client.set("reviewer:%s" % request.user.id, 'online', settings.MAX_IDLE_TIME)
            pass
        stime = get_tomorrow() - timedelta(14)
        etime = get_tomorrow()
        query_time = Q(create_at__lt=etime, create_at__gt=stime)
        query_status = Q(status='0') | Q(status='i') | Q(status='w')
        query_type = Q(type='0') | Q(type='s')
        owner_id = request.GET.get("owner_id")
        query_owner = Q(review__reviewer__user__id=None)
        apply_list = Apply.objects.filter(query_time & query_status & query_type & query_owner).distinct()
        # if apply_list:
            # apply_list = [int(a.id) for a in apply_list]
            # execute_dispatch.apply_async(args=(apply_list, 'change_status', {}), queue_name='dispatch')

    except Exception as error:
        traceback.print_exc()
        Log().error(str(error))
        return HttpResponse(json.dumps({"error": u"状态修改失败,请联系管理员！"}))
    return HttpResponse(json.dumps({"result": "ok", }))


def set_expect_tasks(request):
    pass


def _add_task_apply(apply_id, reviewer_id, apply_type):
    date = datetime.now().date().strftime('%Y%m%d')
    tasks_table = mongo_client['dispatch']['tasks']
    record_table = mongo_client['dispatch']['daily_records']
    open_tasks = mongo_client['dispatch']['open_tasks']
    wait_dispatch_table = mongo_client['dispatch']['wait_dispatch']
    # data = record_table.find_one({'day': date}, {'data': 1, '_id': 0})
    start_time = datetime.now()

    if tasks_table:
        old_record = tasks_table.update({"task_list": apply_id}, {"$pull": {"task_list": apply_id}})
        old_task = wait_dispatch_table.update({}, {"$pull": {"apply_ids": apply_id}})
        reviewer_tasks = open_tasks.find_one({"reviewer_id": reviewer_id})
        if reviewer_tasks:
            result = open_tasks.update({"reviewer_id": reviewer_id},
                              {"$addToSet":
                                   {"task_list": {"$each":
                                                      [{'apply_id': apply_id, 'start': start_time,
                                                        'end': '', 'cost_time': '', 'result': '',
                                                        'type': apply_type}]
                                                  }}})
        else:
            result = open_tasks.insert({"reviewer_id": reviewer_id,
                               "task_list": [{'apply_id': apply_id, 'start': start_time,
                                              'end': '', 'cost_time': '', 'result': '',
                                              'type': apply_type}]})
        # result = record_table.update({"day": date, "data.reviewer_id": str(reviewer_id)},
        #                     {"$addToSet":
        #                        {"data.$.apply_list": {"$each":
        #                            [{'apply_id': apply_id, 'start': start_time,
        #                               'end': '', 'cost_time': '', 'result': '', 'type': apply_type}]
        #                     }}})
    else:
        result = 'error not init daily table!'
    return result


def _finish_task_apply(apply_id, reviewer_id, apply_type, apply_result):
    start_time = datetime.now()
    end_time = datetime.now()
    day = datetime.now().date().strftime('%Y%m%d')
    open_tasks = mongo_client['dispatch']['open_tasks']
    record_table = mongo_client['dispatch']['daily_records']
    query_dict = {"reviewer_id": reviewer_id}
    apply_data = open_tasks.find_one({"task_list.apply_id": int(apply_id)}, {"task_list.$": 1})
    if not apply_data:
        apply_data = {'task_list': [{'apply_id': apply_id, 'start': start_time,
                                              'end': '', 'cost_time': '', 'result': '',
                                              'type': apply_type}]}
    apply_info = apply_data['task_list'][0]
    cost_time = end_time - apply_info['start']
    apply_info.update({"end": end_time, "result": apply_result, "cost_time": cost_time.seconds})
    update_dict = {"$pull": {"task_list": {"apply_id": apply_id}}}
    open_tasks.update(query_dict, update_dict, upsert=False, multi=True)
    result = record_table.update({"day": day, "data.reviewer_id": str(reviewer_id)},
                                 {"$addToSet":
                                      {"data.$.apply_list": {"$each":
                                                                 [apply_info]
                                                             }}})
    all_tasks = record_table.find_one({"day": day, "data.reviewer_id": str(reviewer_id)}, {"data.$": 1})['data'][0]

    total_time = 0
    average_time = 0
    if all_tasks['apply_list']:
        total_time = reduce(lambda x, y: x + y, [i['cost_time'] for i in all_tasks['apply_list']])
        average_time = total_time / len(all_tasks['apply_list'])
        first_pass_lists = [i['cost_time'] for i in all_tasks['apply_list'] if i['result'] == 'y' and i['type'] == '0']
        first_pass_mount = len(first_pass_lists)
        second_pass_lists = [i['cost_time'] for i in all_tasks['apply_list'] if i['result'] == 'y' and i['type'] == 's']
        second_pass_mount = len(second_pass_lists)
        pass_lists = first_pass_lists + second_pass_lists
        pass_mount = first_pass_mount + second_pass_mount
        first_reject_lists = [i['cost_time'] for i in all_tasks['apply_list'] if
                              i['result'] == 'n' and i['type'] == '0']
        first_reject_mount = len(first_reject_lists)
        second_reject_lists = [i['cost_time'] for i in all_tasks['apply_list'] if
                               i['result'] == 'n' and i['type'] == 's']
        second_reject_mount = len(second_reject_lists)
        reject_lists = first_reject_lists + second_reject_lists
        reject_mount = first_reject_mount + second_reject_mount
        first_back_lists = [i['cost_time'] for i in all_tasks['apply_list'] if i['result'] == 'r' and i['type'] == '0']
        first_back_mount = len(first_back_lists)
        second_back_lists = [i['cost_time'] for i in all_tasks['apply_list'] if i['result'] == 'r' and i['type'] == 's']
        second_back_mount = len(second_back_lists)
        back_lists = first_back_lists + second_back_lists
        back_mount = len(back_lists)
        pass_total_time = sum(pass_lists)
        pass_average_time = pass_total_time / pass_mount if pass_mount else 0
        reject_total_time = sum(reject_lists)
        reject_average_time = reject_total_time / reject_mount if reject_mount else 0
        record_table.update({"day": day, "data.reviewer_id": str(reviewer_id)},
                            {"$set": {"data.$.total_time": total_time, "data.$.average_time": average_time,
                                      "data.$.pass_average_time": pass_average_time,
                                      "data.$.reject_average_time": reject_average_time,
                                      "data.$.pass_total_time": pass_total_time,
                                      "data.$.first_pass_mount": first_pass_mount,
                                      "data.$.reject_total_time": reject_total_time,
                                      "data.$.first_pass_mount": first_pass_mount,
                                      "data.$.first_reject_mount": first_reject_mount,
                                      "data.$.first_back_mount": first_back_mount,
                                      "data.$.second_pass_mount": second_pass_mount,
                                      "data.$.second_reject_mount": second_reject_mount,
                                      "data.$.second_back_mount": second_back_mount,
                                      "data.$.pass_mount": pass_mount,
                                      "data.$.reject_mount": reject_mount,
                                      "data.$.back_mount": back_mount,
                                      }})
        today_data = record_table.find_one({"day": day}, {"_id": 0})
        per_today_total_tasks = len(all_tasks['apply_list'])
        record_table.update({"day": day, "data.reviewer_id": str(reviewer_id)},
                            {"$set": {"data.$.today_total_tasks": per_today_total_tasks}})
        today_total_tasks = reduce(lambda x, y: x + y, [len(i['apply_list']) for i in today_data['data']])
        record_table.update({"day": day}, {"$set": {"today_total_tasks": today_total_tasks}})
    return result


# @page_permission(check_employee)
def get_dashboard_data(request, *args, **kwargs):
    if not request.user.id:
        return HttpResponseRedirect('/accounts/login/')
    if request.method == 'GET':
        mod_params = request.GET.get("mod_params")
    staff = Employee.objects.get(user=request.user)
    record_table = mongo_client['dispatch']['daily_records']
    day = datetime.now().date()
    day_str = datetime.now().date().strftime('%Y%m%d')
    yesterday = day - timedelta(days=1)
    yesterday_str = yesterday.strftime('%Y%m%d')
    today_data = record_table.find_one({"day": day_str}, {"_id": 0})
    yesterday_data = record_table.find_one({"day": yesterday_str}, {"_id": 0})
    if staff.post in ['rm', 'r2', 'ad'] and not mod_params:
        # if mod_params == 'mo':
        if today_data:
            today_total_tasks = today_data['today_total_tasks']
            today_expect_tasks = today_data['today_expect_tasks']
            today_overdue_num = today_data['total_overdue_num']
            #  当天实时通过率
            pass_today_percents = sum([i['pass_mount'] for i in today_data['data']]) / float(
                today_total_tasks) if today_total_tasks > 0 else 0
            pass_today_percents = round(pass_today_percents, 2)
            #  实时单量完成情况
            today_total_percents = today_total_tasks / 10000.00
            # 今日整体平均做单时长
            global_t_average_times = sum(
                [i['total_time'] for i in today_data['data']]) / today_total_tasks if today_total_tasks else 0
        else:
            today_total_tasks = 0
            today_overdue_num = 0
            today_expect_tasks = 10000
            today_total_percents = 0
            pass_today_percents = 0
            global_t_average_times = 0
        # 昨日整体平均做单时长
        if yesterday_data:
            yesterday_total_tasks = yesterday_data['today_total_tasks']
            yesterday_overdue_num = yesterday_data['total_overdue_num'] if 'total_overdue_num' in yesterday_data else 0

            global_y_average_times = sum([i['total_time'] for i in yesterday_data[
                'data']]) / yesterday_total_tasks if yesterday_total_tasks else 0

        else:
            yesterday_overdue_num = 0
            global_y_average_times = 0
        global_y_average_times = time.strftime('%H:%M:%S', time.gmtime(global_y_average_times))
        global_t_average_times = time.strftime('%H:%M:%S', time.gmtime(global_t_average_times))

        data = {"real_time_pass_rate": pass_today_percents * 100.00,
                "real_time_done_num": today_total_tasks, "expect_done_num": today_expect_tasks,
                "apply_process_time_avg_yesterday": global_y_average_times,
                "apply_process_time_avg": global_t_average_times,
                "apply_overdue_num": today_overdue_num, "apply_overdue_num_yesterday": yesterday_overdue_num
                }
        page = render_to_response('review/review_manager_overview.html', data,
                                  context_instance=RequestContext(request))
    elif staff.post in ['rs'] or (staff.post in ['rm', 'r2', 'ad'] and mod_params == 'mine'):
        # elif mod_params == 'eo':
        employee_today_data = [i for i in today_data['data'] if i['reviewer_id'] == str(staff.user.id)]
        if yesterday_data:
            employee_yesterday_data = [i for i in yesterday_data['data'] if i['reviewer_id'] == str(staff.user.id)]
        else:
            employee_yesterday_data = []
        if employee_yesterday_data:
            # 昨日审批总时长
            yesterday_total_time = employee_yesterday_data[0]['total_time']

            # 昨日 通过单 审批平均时长
            yesterday_pass_average_time = employee_yesterday_data[0]['pass_average_time']
            # 昨日 拒绝单 审批平均时长
            yesterday_reject_average_time = employee_yesterday_data[0]['reject_average_time']

            # 昨日首次审批通过单量
            yesterday_f_pass_mount = employee_yesterday_data[0]['first_pass_mount']
            # 昨日首次审批拒绝单量
            yesterday_f_reject_mount = employee_yesterday_data[0]['first_reject_mount']
            # 昨日首次审批打回单量
            yesterday_f_back_mount = employee_yesterday_data[0]['first_back_mount']

            # 昨日二次审批通过单量
            yesterday_s_pass_mount = employee_yesterday_data[0]['second_pass_mount']
            # 昨日二次审批拒绝单量
            yesterday_s_reject_mount = employee_yesterday_data[0]['second_reject_mount']
            # 昨日二次审批打回单量
            yesterday_s_back_mount = employee_yesterday_data[0]['second_back_mount']
        else:
            yesterday_total_time = 0
            yesterday_pass_average_time, yesterday_reject_average_time = 0, 0
            yesterday_f_pass_mount, yesterday_f_reject_mount, yesterday_f_back_mount = 0, 0, 0
            yesterday_s_pass_mount, yesterday_s_reject_mount, yesterday_s_back_mount = 0, 0, 0

        today_total_time = 0
        today_f_back_mount, today_f_pass_mount, today_f_reject_mount = 0, 0, 0
        today_s_pass_mount, today_s_reject_mount, today_s_back_mount = 0, 0, 0
        if employee_today_data:
            # 今日审批时长
            today_total_time = employee_today_data[0]['total_time']

            # 今日首次审批通过单量
            today_f_pass_mount = employee_today_data[0]['first_pass_mount']
            # 今日首次审批拒绝单量
            today_f_reject_mount = employee_today_data[0]['first_reject_mount']
            # 今日首次审批打回单量
            today_f_back_mount = employee_today_data[0]['first_back_mount']
            # 今日二次审批通过单量
            today_s_pass_mount = employee_today_data[0]['second_pass_mount']
            # 今日二次审批拒绝单量
            today_s_reject_mount = employee_today_data[0]['second_reject_mount']
            # 今日二次审批打回单量
            today_s_back_mount = employee_today_data[0]['second_back_mount']
        today_total_time = time.strftime('%H:%M:%S', time.gmtime(today_total_time))
        yesterday_total_time = time.strftime('%H:%M:%S', time.gmtime(yesterday_total_time))
        yesterday_pass_average_time = time.strftime('%H:%M:%S', time.gmtime(yesterday_pass_average_time))
        yesterday_reject_average_time = time.strftime('%H:%M:%S', time.gmtime(yesterday_reject_average_time))
        data = {"work_time_today": today_total_time, "work_time_yesterday": yesterday_total_time,
                "overview_time_today": today_total_time, "overview_time_yesterday": yesterday_total_time,
                "apply_pass_time_avg_yesterday": yesterday_pass_average_time,
                "apply_reject_time_avg_yesterday": yesterday_reject_average_time,
                "chart": {"apply_review": [today_f_pass_mount, today_f_reject_mount, today_f_back_mount],
                          "second_loan_review": [today_s_pass_mount, today_s_reject_mount, today_s_back_mount],
                          "apply_review_yesterday": [yesterday_f_pass_mount, yesterday_f_reject_mount,
                                                     yesterday_f_back_mount],
                          "second_loan_review_yesterday": [yesterday_s_pass_mount, yesterday_s_reject_mount,
                                                           yesterday_s_back_mount]},
                }
        page = render_to_response('review/review_employee_overview.html', data,
                                  context_instance=RequestContext(request))
    else:
        page = HttpResponseRedirect('mine')
    return page

# @page_permission(check_employee)
def get_manager_overview_html(request):
    if request.method == 'GET':
        data = {
            "expect_done_num": 10000,
            "real_time_done_num": 3148,
            "real_time_pass_rate": 85.6,
            "apply_process_time_avg": "00:34:11",
            "apply_process_time_avg_yesterday": '00:34:11',
            "apply_overdue_num": 21,
            "apply_overdue_num_yesterday": 2,
            "last_time": "2016-04-07",
            "members": [{"id": i, "name": i} for i in range(1, 20)]
        }
        page = render_to_response('review/review_manager_overview.html', data, context_instance=RequestContext(request))
        return page


def get_employee_overview_html(request):
    if request.method == 'GET':
        data = dict(
            work_time_today="00:44:12",
            work_time_yesterday="02:12:44",
            overview_time_today="00:12:54",
            overview_time_yesterday="01:12:11",
            apply_pass_time_avg_yesterday="00:02:48",
            apply_reject_time_avg_yesterday="00:09:11",
            last_time="2016-04-07",
            chart={
                "apply_review": [100, 200, 300, 600],
                "apply_review_yesterday": [102, 202, 302, 602],
                "second_loan_review": [10, 20, 30, 60],
                "second_loan_review_yesterday": [12, 22, 32, 62],
            },
            m0_client=[
                dict(client_name=1, client_id=1, client_repay_time="2016-04-05"),
                dict(client_name=2, client_id=2, client_repay_time="2016-04-06"),
                dict(client_name=3, client_id=3, client_repay_time="2016-04-07"),
                dict(client_name=4, client_id=4, client_repay_time="2016-04-08"),
                dict(client_name=5, client_id=5, client_repay_time="2016-04-09"),
                dict(client_name=6, client_id=6, client_repay_time="2016-04-10"),
            ],
            overdue_client=[
                dict(client_name=1, client_id=1, client_repay_time="2016-04-05", client_overdue_day=1),
                dict(client_name=2, client_id=2, client_repay_time="2016-04-06", client_overdue_day=2),
                dict(client_name=3, client_id=3, client_repay_time="2016-04-07", client_overdue_day=3),
                dict(client_name=4, client_id=4, client_repay_time="2016-04-08", client_overdue_day=4),
                dict(client_name=5, client_id=5, client_repay_time="2016-04-09", client_overdue_day=5),
                dict(client_name=6, client_id=6, client_repay_time="2016-04-10", client_overdue_day=6),
            ]
        )
        page = render_to_response('review/review_employee_overview.html', data,
                                  context_instance=RequestContext(request))
        return page


@page_permission(check_employee)
def get_review_id_view(request):
    if request.method == 'GET':
        columns = data_views.get_order_columns()
        # columns = review_views.get_review_columns()
        page = render_to_response('review/order_review.html', {"columns": columns, "datatable": []},
                                  context_instance=RequestContext(request))
        return page


def _get_user_info(request, user):
    '''
        获取用户的相关信息
    '''
    start = time.time()
    Log().debug("start get user data: %f" % start)
    applyer = user
    profiles = Profile.objects.filter(owner=applyer)
    profile = profiles[0] if len(profiles) == 1 else None
    chsis = Chsi.objects.filter(user=applyer).order_by('-id')[:1]
    for chsi in chsis:
        if chsi.chsi_name.startswith("file"):
            chsi.chsi_name_img = chsi.chsi_name
            chsi.chsi_name = ""
    Log().debug("chsi %f" % (time.time() - start))
    idcards = IdCard.objects.filter(owner=applyer)
    idcard = idcards[0] if len(idcards) == 1 else None
    contacts = ContactInfo.objects.filter(owner=applyer).order_by('-id')
    if len(contacts) > 3:
        contacts = contacts[0:3]
        contacts.reverse()
    bankcards = BankCard.objects.filter(Q(owner=applyer) & ~Q(card_type=4))
    # for bankcard in bankcards:
        # same_ids = BankCard.objects.filter(Q(number=bankcard.number) & ~Q(user=bankcard.user))
        # bankcard.card_repeat = len(same_ids)
        # bankcard.cards = same_ids[:10]
    Log().debug("bankcard %f" % (time.time() - start))
    check_status = CheckStatus.objects.get(owner=applyer)
    # if check_status.auto_check_status == 0:
    #    check_status = None
    same_ids = User.objects.filter(device_id=applyer.device_id)
    device_id_repeat = len(same_ids)
    ids = same_ids[:10]
    Log().debug("same id %f" % (time.time() - start))
    register_ip = None
    try:
        register_ip = redis_client.hget("USER_INFO:%d" % applyer.id, "ip")
    except Exception, e:
        Log().error(u"_get_user_info call redis error")
    Log().debug("register ip %f" % (time.time() - start))
    ip_address = ""
    chsi_auths = Chsiauthinfo.objects.filter(user_id=applyer.id).order_by("-id")
    chsi_auth = chsi_auths[0] if len(chsi_auths) == 1 else None
    if chsi_auth and chsi_auth.username:
        try:
            cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_KEY)
            chsi_auth.username = cipher.decrypt(base64.b64decode(chsi_auth.username.strip('\0')))
        except:
            chsi_auth.username = ''
    # if register_ip:
    #    ip_address = ip_client.ip2address(register_ip)
    review_dict = {"user": applyer, "bankcards": bankcards, 'oss_url': settings.OSS_URL, "check_status": check_status,
                   "chsis": chsis, 'profile': profile, "idcard": idcard, 'chsi_auth': chsi_auth,
                   "device_id_repeat": device_id_repeat, "ids": ids,
                   "register_ip": register_ip, "ip_address": ip_address}
    Log().debug("end %f" % (time.time() - start))
    return review_dict


def _get_interface_data(request, user):
    # get data from data_server
    start = time.time()
    review_dict = {}
    applyer = user
    profiles = Profile.objects.filter(owner=applyer)
    profile = profiles[0] if len(profiles) == 1 else None
    contacts = ContactInfo.objects.filter(owner=applyer).order_by('-id')
    if profile and profile.job == 2:
        review_dict["has_ebusiness"] = True
    else:
        review_dict["has_ebusiness"] = False
    has_new_data = None
    try:
        has_new_data = redis_client.hget("USER_INFO:%d" % applyer.id, "mobile_record")
    except Exception, e:
        Log().error(u"call redis error")
    # start = time.time()
    # Log().debug("get data from dataserver: %f" % start)
    Log().debug("get basic data done, next from dataserver: %f" % (time.time() - start))

    contacts = ContactInfo.objects.filter(owner=applyer).order_by('-id')
    if len(contacts) > 3:
        contacts = contacts[0:3]
        contacts.reverse()
    contacts_data = []
    for contact in contacts:
        # same_ids = ContactInfo.objects.filter(Q(phone_no = contact.phone_no) & ~Q(owner = contact.owner))
        contact.contact_repeat = 0
        contact.contacts = None
        name_inaddressbook = AddressBook.objects.filter(owner=applyer, phone_number=contact.phone_no)
        addressbook_name = name_inaddressbook[0].name if name_inaddressbook else ' '
        contact_data = (contact, addressbook_name,)
        if contact.phone_no:
            contacts_data.append(contact_data)

    if has_new_data and settings.USE_DATA_SERVER:
        review_dict["new_data"] = True
        basic_data = data_query.basic_data.copy()
        basic_data["user_id"] = applyer.id
        phone_basics = data_query.get_phonebasic_data(basic_data)
        review_dict["phone_basics"] = phone_basics
        Log().debug("phone basic %f" % (time.time() - start))

        phone_data = data_query.phone_data.copy()
        phone_data["user_id"] = applyer.id
        phone_data["contact"] = []
        for contact in contacts:
            phone_data["contact"].append(
                {"contact_name": contact.name, "contact_type": contact.relationship, "contact_tel": contact.phone_no})
        contact_phone_calls, contact_phone_call_columns = data_query.get_phonecall_data(phone_data)
        review_dict["contact_phone_call_columns"] = contact_phone_call_columns
        review_dict["contact_phone_calls"] = contact_phone_calls

        corp_data = data_query.corp_data.copy()
        corp_data["user_id"] = applyer.id
        (corp_contact_phone_calls, corp_contact_phone_call_columns) = data_query.get_corp_phonecall_data(corp_data)
        review_dict["corp_contact_phone_call_columns"] = corp_contact_phone_call_columns
        review_dict["corp_contact_phone_calls"] = corp_contact_phone_calls
        Log().debug("corp contact %f" % (time.time() - start))

        ebusiness_data = data_query.ebusiness_data.copy()
        ebusiness_data["user_id"] = applyer.id
        e_business = data_query.get_ebusiness_data(ebusiness_data)
        review_dict["e_business"] = e_business
        Log().debug("ebusiness %f" % (time.time() - start))

        deliver_data = data_query.deliver_data.copy()
        deliver_data["user_id"] = applyer.id
        e_deliver = data_query.get_deliver_data(deliver_data)
        review_dict["e_deliver"] = e_deliver
        Log().debug("edeliver %f" % (time.time() - start))

        phone_location_data = data_query.phone_location_data.copy()
        phone_location_data["user_id"] = applyer.id
        phone_location = data_query.get_phone_location_data(phone_location_data)
        review_dict["phone_location"] = phone_location
        Log().debug("phone location %f" % (time.time() - start))
        addresses = AddressBook.objects.filter(owner=applyer).order_by('id')
        address = addresses[:10]
        review_dict["addressbook"] = address
        review_dict["addressbooks"] = addresses
    else:
        review_dict["new_data"] = False
        basic_data = data_query.basic_data.copy()
        basic_data["user_id"] = applyer.id
        phone_basics = data_query.get_phonebasic_data(basic_data)
        review_dict["phone_basics"] = phone_basics
        Log().debug("phone basic %f" % (time.time() - start))

        phone_data = data_query.phone_data.copy()
        phone_data["user_id"] = applyer.id
        phone_data["contact"] = []
        for contact in contacts:
            phone_data["contact"].append(
                {"contact_name": contact.name, "contact_type": contact.relationship, "contact_tel": contact.phone_no})
        contact_phone_calls, contact_phone_call_columns = data_query.get_phonecall_data(phone_data)
        review_dict["contact_phone_call_columns"] = contact_phone_call_columns
        review_dict["contact_phone_calls"] = contact_phone_calls

        corp_data = data_query.corp_data.copy()
        corp_data["user_id"] = applyer.id
        (corp_contact_phone_calls, corp_contact_phone_call_columns) = data_query.get_corp_phonecall_data(corp_data)
        review_dict["corp_contact_phone_call_columns"] = corp_contact_phone_call_columns
        review_dict["corp_contact_phone_calls"] = corp_contact_phone_calls
        Log().debug("corp contact %f" % (time.time() - start))

        ebusiness_data = data_query.ebusiness_data.copy()
        ebusiness_data["user_id"] = applyer.id
        e_business = data_query.get_ebusiness_data(ebusiness_data)
        review_dict["e_business"] = e_business
        Log().debug("ebusiness %f" % (time.time() - start))

        deliver_data = data_query.deliver_data.copy()
        deliver_data["user_id"] = applyer.id
        e_deliver = data_query.get_deliver_data(deliver_data)
        review_dict["e_deliver"] = e_deliver
        Log().debug("edeliver %f" % (time.time() - start))

        phone_location_data = data_query.phone_location_data.copy()
        phone_location_data["user_id"] = applyer.id
        phone_location = data_query.get_phone_location_data(phone_location_data)
        review_dict["phone_location"] = phone_location
        # TODO: 延迟加载address和callrecord
        addresses = AddressBook.objects.filter(owner=applyer).order_by('id')
        address = addresses[:10]
        Log().debug("addressbook %f" % (time.time() - start))
        review_dict["addressbook"] = address
        review_dict['addressbooks'] = addresses
        # print "位置", phone_location
        # print "电话", phone_basics
        # print "联系人", contact_phone_calls
        # print "公司", corp_contact_phone_calls
        # print "电商", e_business
        # print "快递", e_deliver

    chsis = Chsi.objects.filter(user=applyer).order_by('-id')[:1]
    for chsi in chsis:
        if chsi.chsi_name.startswith("file"):
            chsi.chsi_name_img = chsi.chsi_name
            chsi.chsi_name = ""

    idcards = IdCard.objects.filter(owner=applyer)
    idcard = idcards[0] if len(idcards) == 1 else None

    review_dict["contacts"] = contacts_data
    review_dict["chsis"] = chsis
    review_dict["idcard"] = idcard
    review_dict["oss_url"] = settings.OSS_URL
    review_dict["user"] = applyer

    return review_dict


def _get_review_label():
    labels = Label.get_all_label()
    return {"labels": labels}


def _get_review_info(request, apply):
    reviews = Review.objects.filter(order=apply).order_by("-finish_time")
    # TODO: 延迟加载review
    show_reviews = {}
    labels = []
    if len(reviews) >= 1:
        # show_reviews["id_review"] = ReviewRecord.objects.filter(review__in=reviews, review_type='i').order_by("-id")
        # show_reviews["work_review"] = ReviewRecord.objects.filter(review__in=reviews, review_type='w').order_by("-id")
        show_reviews["chsi_review"] = ReviewRecord.objects.filter(review__in=reviews, review_type='c').order_by("-id")
        # show_reviews["family_review"] = ReviewRecord.objects.filter(review__in=reviews, review_type='f').order_by("-id")
        # show_reviews["bank_review"] = ReviewRecord.objects.filter(review__in=reviews, review_type='b').order_by("-id")
        show_reviews["action_review"] = ReviewRecord.objects.filter(review__in=reviews, review_type='a').order_by("-id")
        # show_reviews["pic_front_review"] = ReviewRecord.objects.filter(review__in=reviews, review_type='p').order_by(
            # "-id")
        # show_reviews["pic_back_review"] = ReviewRecord.objects.filter(review__in=reviews, review_type='o').order_by(
            # "-id")
        # show_reviews["pic_hand_review"] = ReviewRecord.objects.filter(review__in=reviews, review_type='q').order_by(
            # "-id")
        # show_reviews["e_business_review"] = ReviewRecord.objects.filter(review__in=reviews, review_type='e').order_by(
            # "-id")
        labels = reviews[0].get_label_list().all()

    return {"apply": apply, "reviews": show_reviews, "labels": labels}


def _get_info_by_apply(request, apply_id):
    apply_info = Apply.objects.get(pk=apply_id)
    apply_dict = _get_review_info(request, apply_info)
    user_dict = _get_user_info(request, apply_info.create_by)
    all_dict = user_dict.copy()
    all_dict.update(apply_dict)
    return all_dict


def _get_last_basic_apply(user):
    try:
        applys = Apply.objects.filter(create_by=user, type='0').order_by("-id")
        last_apply = applys[0] if len(applys) > 0 else None
        return last_apply
    except Exception, e:
        traceback.print_exc()
        return None


def _get_last_review(apply_order):
    try:
        reviews = Review.objects.filter(order=apply_order).order_by("-id")
        last_review = reviews[0] if len(reviews) > 0 else None
        return last_review
    except Exception, e:
        traceback.print_exc()
        return None


def get_info_by_user(request, user_id):
    '''
        返回用户和他最近一次基础信息的审批数据
    '''
    try:
        user = User.objects.get(pk=user_id)
        user_dict = _get_user_info(request, user)
        all_dict = user_dict.copy()
        last_apply = _get_last_basic_apply(user)
        if last_apply:
            apply_dict = _get_review_info(request, last_apply)
            all_dict.update(apply_dict)
        return all_dict
    except Exception, e:
        return {}


def _get_loan_info(request, apply_id):
    apply = Apply.objects.get(pk=apply_id)
    repaymentinfo_list = RepaymentInfo.objects.filter(user=apply.create_by).order_by('-apply_time')

    data_list = list()
    for repaymentinfo in repaymentinfo_list:
        repay_temp_dict = dict()
        repay_temp_dict['order_number'] = repaymentinfo.order_number
        repay_temp_dict['apply_amount'] = round(float(repaymentinfo.apply_amount) / 100, 2)
        repay_temp_dict['exact_amount'] = round(float(repaymentinfo.exact_amount) / 100, 2)
        repay_temp_dict['repay_status'] = repaymentinfo.get_repay_status_display()
        repay_temp_dict['apply_time'] = repaymentinfo.apply_time.strftime(
            "%Y-%m-%d %H:%M:%S") if repaymentinfo.apply_time is not None else ""
        installment_list = InstallmentDetailInfo.objects.filter(repayment_id=repaymentinfo.id).order_by(
            'installment_number')
        repay_temp_dict['install_list'] = list()
        for installment in installment_list:
            install_temp_dict = dict()
            install_temp_dict['installment_number'] = installment.installment_number
            install_temp_dict['should_repay_time'] = installment.should_repay_time.strftime(
                "%Y-%m-%d %H:%M:%S") if installment.should_repay_time is not None else ""
            install_temp_dict['real_repay_time'] = installment.real_repay_time.strftime(
                "%Y-%m-%d %H:%M:%S") if installment.real_repay_time is not None else ""
            install_temp_dict['should_repay_amount'] = round(float(installment.should_repay_amount) / 100, 2)
            install_temp_dict['real_repay_amount'] = round(float(installment.real_repay_amount) / 100,
                                                           2) if installment.real_repay_amount != -1 else 0
            install_temp_dict['repay_status'] = installment.get_repay_status_display()
            repay_temp_dict['install_list'].append(install_temp_dict)

        data_list.append(repay_temp_dict)

    output_data = {'data': data_list}
    return output_data


# @page_permission(check_employee)
def get_report_page(request, apply_id):
    try:
        result = {}
        # employer = Employee.objects.get(user=request.user)
        out_report_url = get_out_page(request, apply_id)
        third_result = get_third_page(request, apply_id)
        interview_result = get_interview_page(request, apply_id)
        if out_report_url :
            result.update(out_report_url)
        if third_result :
            result.update(third_result)
        if interview_result :
            result.update(interview_result)
        return result
        # return HttpResponse(result)
    except PermissionDenied as e:
        return {}



def get_out_page(request, apply_id):
    try:
        employer = Employee.objects.get(user=request.user)
        # if employer.post in ['ra', 'rb', 'rc', 'ad']:
            # print 'have ra permission'
        apply_info = Apply.objects.get(pk=apply_id)
        # review_obj = Review.objects.filter(order=apply_info).order_by('-id')[0]
        reviews = Review.objects.filter(order=apply_info).order_by('-id')
        review_obj = reviews.first()
        if not review_obj.finish_time:
            review_obj = reviews[1]

        review_record_obj = ReviewRecord.objects.filter(review_id=review_obj.id, review_type='b')[0]
        out_report_url = review_record_obj.review_note
        out_report_url = out_report_url.strip()
        return {'url': out_report_url, 'u_status': review_record_obj.review_status, 'url_cut': out_report_url[:20] + "..."}
        # else:
            # return None
    except Exception as e:
        return {}


def get_third_page(request, apply_id):
    if request.method == 'GET':
        try:
            employer = Employee.objects.get(user=request.user)
            # if employer.post in ['rb', 'rc', 'ad']: 
                # print 'have rb permission'
            apply_info = Apply.objects.get(pk=apply_id)

            reviews = Review.objects.filter(order=apply_info).order_by('-id')
            review_obj = reviews.first()
            if not review_obj.finish_time:
                review_obj = reviews[1]
            review_record_obj = ReviewRecord.objects.filter(review_id=review_obj.id, review_type='t')[0]
            third_result = review_record_obj.review_note

            # extra_apply_obj = ExtraApply.objects.filter(apply=apply_info)
            # third_result = extra_apply_obj[0].message_8
            return {'t_result':third_result, 't_status': review_record_obj.review_status}
            # else:
                # return None
        except Exception as e:
            return {}

def get_interview_page(request, apply_id):
    if request.method == 'GET':
        try:
            employer = Employee.objects.get(user=request.user)
            # if employer.post in ['rc', 'ad']:
                # print 'have rc permission'
            apply_info = Apply.objects.get(pk=apply_id)
            
            # review_obj = Review.objects.filter(order=apply_info).order_by('-id')[0]
            reviews = Review.objects.filter(order=apply_info).order_by('-id')
            review_obj = reviews.first()
            if not review_obj.finish_time:
                review_obj = reviews[1]

            review_record_obj = ReviewRecord.objects.filter(review_id=review_obj.id, review_type='c')[0]
            interview_result = review_record_obj.review_note 
            # extra_apply_obj = ExtraApply.objects.filter(apply=apply_info)
            # interview_result = extra_apply_obj[0].message_9
            return {'i_result':interview_result, 'i_status': review_record_obj.review_status}
            # else:
                # return None
        except Exception as e:
            return {}

def __getkey(mydict, vals):
    for key,val in mydict.items():
        if val == int(vals):
            return key

def _format_module(module_set):
    # modules = {}
    modules = []
    for module in module_set:
        m = {"module_name":module["string_module_name"]}
        fields = []
        for field in module["field_set"]:
            if not field["string_user_value"].strip():
                continue

            if field["string_type"] == "radio_button":
                value = __getkey(json.loads(field["string_json"]), field["string_user_value"])
                fields.append({"desc":field["string_desc"], "value":value})
            elif field["string_type"] == "multi_image":
                fields.append({"desc":field["string_desc"], "value":field["string_user_value"].split('|')})
            elif field["string_type"] == "double_dropdown_list":
                dict_list = json.loads(field["string_json"])
                last_name = ""
                for d in dict_list:
                    first_name = d.keys()[0]
                    for v in d.values():
                        for l in v:
                            if l["id"] == int(field["string_user_value"]):
                                last_name = l["name"]
                                break
                        if last_name:
                            break
                fields.append({"desc":field["string_desc"], "value":first_name+last_name})
            elif field["string_type"] == "dropdown_list_with_desc":
                dict_list = json.loads(field["string_json"])
                for d in dict_list:
                    if d["id"] == int(field["string_user_value"]):
                        value = d["name"]+d["desc"]
                fields.append({"desc":field["string_desc"], "value":value})
            elif field["string_type"] == "dropdown_list" and field["string_user_value"].isdigit():
                value = __getkey(json.loads(field["string_json"]), field["string_user_value"])
                fields.append({"desc":field["string_desc"], "value":value})
            else:
                if field["string_name"] == "string_contact":
                    contactor_list = []
                    contactors = field["string_user_value"].split('|')
                    for contactor in contactors:
                        contactor_list.append(contactor.split('_'))
                    fields.append({"desc":field["string_desc"], "value":contactor_list})
                else:
                    fields.append({"desc":field["string_desc"], "value":field["string_user_value"]})
        m["fields"] = fields
        modules.append(m)
    return modules

def __get_statusflow_object_by_apply(apply_obj):
    workflow = apply_obj.workflow
    workstatus = WorkStatus.objects.get(Q(workflow_id=workflow.id) & Q(status_code=apply_obj.status))
    statusflow_obj = StatusFlow.objects.get(Q(flow_id = workflow.id) & Q(status_id=workstatus.id))
    return statusflow_obj

def __get_template_data(apply_id, template_id_set):
    result = []
    print '-> template ids: ', template_id_set
    for template in template_id_set:
        if template:
            template = json.loads(template)
            apply_info = user_center_client.get_user_order(str(apply_id), str(template.get('id')))
            if not apply_info:
                continue
            result.append(apply_info.json_data)
    return result

def __get_template_in_statuflows_set(workflow):
    template_id_set = StatusFlow.objects.filter(flow_id = workflow.id).values_list('template_id', flat = True)
    return template_id_set

def __get_data_server_params(platform_name, product_name):
    platform = Platform.objects.get(name = platform_name)
    product = Product.objects.get(name = product_name, platform = platform_name)
    return platform.org_account, product.service_id

def __get_big_data_report(apply_obj):
    user_id = apply_obj.create_by_id
    headers = {'Content-Type': 'application/json'}
    org_account, service_id = __get_data_server_params(apply_obj.platform, apply_obj.product)
    rsp = requests.post(settings.DATA_SERVER['URL'] + 'get_token', data= json.dumps({'user_id':user_id, 
                                                                                     'org_account':org_account,
                                                                                     'service_id':service_id}), headers=headers)
    return json.loads(rsp.content).get('data')


def __get_review_info_by_apply(apply_obj):
    review_obj_set = apply_obj.review_set.all().filter(~Q(review_res = 0)).order_by('-id')

    result = {}
    if review_obj_set.count() > 0:
        review_obj = review_obj_set[0]
        employee = Employee.objects.get(id=review_obj.reviewer_id)
        result['reviewer'] = employee.username
        if review_obj.finish_time:
            result['review_time'] = review_obj.finish_time.strftime('%Y-%m-%d-%H')
        else:
            result['review_time'] = ''
    else:
        result['reviewer'] = ''
        result['review_time'] = ''
    return result


def __check_permission(request, apply_obj):
    if apply_obj.owner_type != None:
        if apply_obj.owner_type == 0:
            if int(apply_obj.owner_id) != Employee.objects.get(user_id = request.user.id).id:
                employee = Employee.objects.get(user_id=request.user.id)
                pms = employee.get_permission_list()
                _has_permission = 0
                for pm in pms:
                    if pm.permissions and '/review/all' in pm.permissions.split(','):
                        _has_permission = 1
                        break
                if _has_permission:
                    pass
                else:
                    return HttpResponse(__return_json(is_right=False, msg='你没有权限操作。'))
            elif apply_obj.owner_id == request.user.id:
                pass
        elif apply_obj.owner_type == 1:
            staff = Employee.objects.get(user = request.user)
            group_list = json.loads(apply_obj.owner_id)
            group_id_list = map(int, group_list)
            result = list(set(group_id_list).intersection(set(staff.group_list.all().values_list('id', flat=True))))
            if len(result) == 0:
                return HttpResponse(__return_json(is_right=False, msg='你没有权限操作。'))
            elif len(result) > 0:
                pass
    else:
        pass
        # employeegroup_set = EmployeeGroup.objects.filter(id__in=group_id_list)
        # employeegroup = EmployeeGroup.objects.get(id=apply_obj.owner_id)
        # staff = Employee.objects.get(user = request.user)
        # for employeegroup in employeegroup_set:
            # if employeegroup.id not in staff.group_list.all().values_list('id', flat=True):
                # return HttpResponse(__return_json(is_right=False, msg='你没有权限操作。'))
            # elif employeegroup.id in staff.group_list.all().values_list('id', flat=True):
                # pass

#多状态流转获取
def __get_multi_next_status(apply_obj):
    # 返回值：
    # [{'next_status_name':'三方', 'template':{'id':23, 'is_must':1}}, {'next_status_name':'面签', 'template':{'id':24, 'is_must':1}}]
    result = []

    #可以将__get_statusflow_object_by_apply方法中的StatusFlow.objects.get改为StatusFlow.objects.filter后，调用__get_statusflow_object_by_apply
    workflow = apply_obj.workflow
    workstatus = WorkStatus.objects.get(Q(workflow_id=workflow.id) & Q(status_code=apply_obj.status))
    next_status_set = StatusFlow.objects.filter(Q(flow_id = workflow.id) & Q(status_id=workstatus.id))

    next_status_id_set = list(next_status_set.values_list('next_status_id', flat=True))
    workstatus_set = WorkStatus.objects.filter(id__in=next_status_id_set)
    for workstatus in workstatus_set:
        template = next_status_set.get(next_status_id=workstatus.id)
        result.append({'next_status_name':workstatus.other_name if workstatus.other_name else workstatus.name, 'template':template.template_id, 'status':workstatus.status_code})
    return result

# 审批modal页面
# @page_permission(check_employee)
def get_review_info_view(request, apply_id):
    if request.method == 'GET':
        try:
            apply_info = Apply.objects.get(pk=apply_id)
            # _employee = Employee.objects.filter(user=request.user).first()
            # reviews = Review.objects.filter(order = apply_info)
            # if reviews:
            #     if int(apply_info.owner_id) !=  int(_employee.id):
            #         return HttpResponse(json.dumps({'code': -1, 'msg': u'你没有权限操作'}))
            #     else:
            #         pass

            try:
                check_result = __check_permission(request, apply_info)
                if check_result:
                    return check_result
            except Exception as e:
                traceback.print_exc()
                return HttpResponse(json.dumps({'code':-1, 'msg':e.message}))
            key = apply_info.create_by.id_no
            url = 'http://{0}:{1}/get_submitted_profile?search_key={2}&product={3}&platform={4}'.format(settings.WEB_HTTP_SERVER['HOST'],
                                                                                                   settings.WEB_HTTP_SERVER['PORT'],
                                                                                                   key,
                                                                                                   apply_info.product,
                                                                                                   apply_info.platform)
            data = requests.get(url).json()

            template_id_set = __get_template_in_statuflows_set(apply_info.workflow) #获取审批模板集合

            review_add_data = __get_template_data(apply_id, template_id_set) #获取已填写模板内容
            data['review_add_data'] = review_add_data

            if apply_info.status not in ['y', 'n', 'r']:
                #next_status_info_set = __get_multi_next_status(apply_info)
                # data['next_status'] = next_status_info_set
                statusflow_obj = __get_statusflow_by_apply(apply_info) #获取下一步骤需要填写模板id
                data['next_status_template_id'] = statusflow_obj.template_id

                if statusflow_obj.next_status_id == -1: #获取下一个状态名称
                    next_status = WorkStatus.objects.get(Q(workflow_id=apply_info.workflow_id) & Q(status_code='y'))
                else:
                    next_status = WorkStatus.objects.get(id=statusflow_obj.next_status_id) 
                data['next_status_name'] = next_status.other_name if next_status.other_name else next_status.name

            if apply_info.status != 'r':
                current_status = WorkStatus.objects.get(Q(workflow_id=apply_info.workflow.id) & Q(status_code=apply_info.status)) #获取当前状态名称
                data['current_status_name'] = current_status.other_name if current_status.other_name else current_status.name
            elif apply_info.status == 'r':
                data['current_status_name'] = '打回修改'

            data['comment'] = apply_info.comment #获取评论

            info = __get_review_info_by_apply(apply_info) #获取审批信息
            data.update(info)

            report_url = __get_big_data_report(apply_info) #获取大数据url
            data['report_url'] = report_url

            dic = {
                "string_name": "贷款策略",
                "string_description": "策略说明",
                "int32_amount": "贷款金额",
                "string_reason": "贷款用途",
                "string_address": "账单地址",
            }
            try:
                strategy_info = data['logic_rsp']['strategy_info']
            except Exception as e:
                return HttpResponse(__return_json(is_right=False, msg=data['msg']))
            data['logic_rsp']['strategy_info'] = { dic.get(k, k): v for k, v in strategy_info.items() if k not in ['int32_strategy_id']}
            if data['logic_rsp']['strategy_info'].get("贷款金额"):
                data['logic_rsp']['strategy_info']["贷款金额"] = data['logic_rsp']['strategy_info']["贷款金额"] / 100
            
            return HttpResponse(json.dumps(data))
        except Exception as e:
            traceback.print_exc()
            return HttpResponse(json.dumps({'code':-1, 'msg':e.message}))


@page_permission(check_employee)
def get_review_contact_info_view(request, apply_id):
    """ 审批页面的联系人和电商信息"""
    if request.method == 'GET':
        apply_info = Apply.objects.get(pk=apply_id)
        review_contact_dict = _get_interface_data(request, apply_info.create_by)
        # review_contact_dict = {}
        # user = User.objects.get(pk=apply_info.create_by.id)
        apply_dict = _get_review_info(request, apply_info)
        if not apply_dict["reviews"]:
            last_apply = _get_last_basic_apply(apply_info.create_by)
            apply_dict = _get_review_info(request, last_apply)

        review_contact_dict.update(apply_dict)
        # if apply_info.status == 'b':
        # # review_dict = _read_snapshot_apply(request, apply_id)
        # else:
        # review_dict = _get_info_by_apply(request, apply_id)
        # labels = _get_review_label()
        # review_dict.update(labels)
        # if review_dict['check_status'].auto_check_status in (2, 3, 4, -11,):
        # review_dict['check_status'].auto_check_status = 0
        # for f in review_dict['phone_basics']:
        page = render_to_response('review/modal_contact.html', review_contact_dict,
                                  context_instance=RequestContext(request))
        return page


def __return_json(return_obj=None, is_right=True, msg='', content=None):
    result ={'code':0, 'msg':''}
    if is_right:
        if content:
            return json.dumps({'code':0, 'msg':'', 'content':content})
    elif not is_right:
        result.update({'code':-1, 'msg':msg})
        return json.dumps(result)


# @page_permission(check_employee)
def get_data(request):
    if request.method == 'GET':
        apply_id = request.GET.get('apply_id')
        template_id = request.GET.get('template_id')
        apply_info = user_center_client.get_user_order(apply_id, template_id)
        return HttpResponse(__return_json(content=apply_info))



# 查看审批结果modal
# @page_permission(check_employee)
def get_review_view(request, apply_id):
    if request.method == 'GET':
        try:
            apply_info = Apply.objects.get(pk=apply_id)
            #try:
            #    check_result = __check_permission(request, apply_info)
            #    if check_result:
            #        return check_result
            #except Exception as e:
            #    traceback.print_exc()
            #    return HttpResponse(json.dumps({'code':-1, 'msg':e.message}))

            key = apply_info.create_by.id_no
            url = 'http://{0}:{1}/get_submitted_profile?search_key={2}&product={3}&platform={4}'.format(settings.WEB_HTTP_SERVER['HOST'],
                                                                                                   settings.WEB_HTTP_SERVER['PORT'],
                                                                                                   key,
                                                                                                   apply_info.product,
                                                                                                   apply_info.platform)
            data = requests.get(url).json()

            template_id_set = __get_template_in_statuflows_set(apply_info.workflow) #获取审批模板集合

            review_add_data = __get_template_data(apply_id, template_id_set) #获取已填写模板内容
            data['review_add_data'] = review_add_data

            if apply_info.status not in ['y', 'n', 'r']:
                #next_status_info_set = __get_multi_next_status(apply_info)
                # data['next_status'] = next_status_info_set
                statusflow_obj = __get_statusflow_by_apply(apply_info) #获取下一步骤需要填写模板id
                data['next_status_template_id'] = statusflow_obj.template_id

                if statusflow_obj.next_status_id == -1: #获取下一个状态名称
                    next_status = WorkStatus.objects.get(Q(workflow_id=apply_info.workflow_id) & Q(status_code='y'))
                else:
                    next_status = WorkStatus.objects.get(id=statusflow_obj.next_status_id) 
                data['next_status_name'] = next_status.other_name if next_status.other_name else next_status.name

            if apply_info.status != 'r':
                current_status = WorkStatus.objects.get(Q(workflow_id=apply_info.workflow.id) & Q(status_code=apply_info.status)) #获取当前状态名称
                data['current_status_name'] = current_status.other_name if current_status.other_name else current_status.name
            elif apply_info.status == 'r':
                data['current_status_name'] = '打回修改'

            data['comment'] = apply_info.comment #获取评论

            info = __get_review_info_by_apply(apply_info) #获取审批信息
            data.update(info)

            report_url = __get_big_data_report(apply_info) #获取大数据url
            data['report_url'] = report_url

            dic = {
                "string_name": "贷款策略",
                "string_description": "策略说明",
                "int32_amount": "贷款金额",
                "string_reason": "贷款用途",
                "string_address": "账单地址",
            }
            try:
                strategy_info = data['logic_rsp']['strategy_info']
            except Exception as e:
                return HttpResponse(__return_json(is_right=False, msg=data['msg']))
            data['logic_rsp']['strategy_info'] = { dic.get(k, k): v for k, v in strategy_info.items() if k not in ['int32_strategy_id']}
            if data['logic_rsp']['strategy_info'].get("贷款金额"):
                data['logic_rsp']['strategy_info']["贷款金额"] = data['logic_rsp']['strategy_info']["贷款金额"] / 100
            return HttpResponse(json.dumps(data))
        except Exception as e:
            traceback.print_exc()
            return HttpResponse(json.dumps({'code':-1, 'msg':e.message}))

# 审批提现信息 modal
@page_permission(check_employee)
def get_review_loan_info_view(request, apply_id):
    if request.method == 'GET':
        all_dict = {}
        try:
            loan_apply = Apply.objects.get(pk=apply_id)
            all_dict = get_info_by_user(request, loan_apply.create_by.id)
            loan_dict = _get_loan_info(request, apply_id)
            all_dict.update(loan_dict)
            all_dict["apply"] = loan_apply
        except Exception, e:
            traceback.print_exc()
            Log().error('get_review_loan_info_view failed: %s' % str(e))
        collection_check = redis_client.hget("collection_check", loan_apply.create_by_id)
        if collection_check:
            check_staff = collection_check.split(":")[0]
            if check_staff:
                staff = Employee.objects.get(user__id=check_staff)
            else:
                staff = ''
            check_result = collection_check.split(":")[1]
            if check_result == '0':
                all_dict.update(
                    {"collection_check": '<span class="label label-danger">%s的二次提现催收意见为:不允许通过</span>' % staff.username})
            elif check_result == '1':
                all_dict.update({
                                    "collection_check": '<span class="label  label-success">%s的二次提现催收意见为:允许通过</span>' % staff.username})
        else:
            all_dict.update({"collection_check": '<span class="label  label-success">默认二次提现催收意见为:允许通过</span>'})
        page = render_to_response('review/modal_loan.html', all_dict, context_instance=RequestContext(request))
        return page


# 查看审批提现信息 modal
@page_permission(check_employee)
def view_loan_info_view(request, apply_id):
    if request.method == 'GET':
        all_dict = {}
        try:
            loan_apply = Apply.objects.get(pk=apply_id)
            all_dict = get_info_by_user(request, loan_apply.create_by.id)
            loan_dict = _get_loan_info(request, apply_id)
            all_dict.update(loan_dict)
            all_dict["apply"] = loan_apply
        except Exception, e:
            traceback.print_exc()

        review_dict = all_dict
        apply_info = loan_apply
        report_dic = get_report_page(request, Apply.objects.filter(create_by_id=apply_info.create_by_id, status='y', type=0).order_by('-id').first().id)
        if not report_dic:
            review_dict.update(report_dic)
        review_dict.update({"report": report_dic})

        phone = apply_info.create_by.phone_no
        url = 'http://{0}:{1}/get_submitted_profile?search_key={2}&product={3}&platform={4}'.format(settings.WEB_HTTP_SERVER['HOST'],
                                                                                               settings.WEB_HTTP_SERVER['PORT'],
                                                                                               phone,
                                                                                               apply_info.product,
                                                                                               apply_info.platform)
        data = requests.get(url).json()
        # value_to_key(data)

        module_set= data['logic_rsp']['module_set']
        review_dict["data"] = _format_module(module_set)

        # review_dict['apply_status'] = apply_info.status

        strategy = Strategy2.objects.filter(strategy_id=apply_info.strategy_id).first()
        if strategy:
            strategy_info = {
            "贷款策略": strategy.strategy_description,
            "策略说明": strategy.description,
            "贷款金额": round(apply_info.amount / 100.0, 2),
            "贷款用途": apply_info.reason,
            "账单地址": apply_info.bill_address,
            "客户经理编号": apply_info.salesman,
            }
            review_dict['strategy_info'] = strategy_info


        page = render_to_response('review/view_modal_loan.html', review_dict, context_instance=RequestContext(request))
        return page


# 审批额度提升 modal
@page_permission(check_employee)
def get_review_promote_info_view(request, apply_id):
    if request.method == 'GET':
        apply = Apply.objects.get(pk=apply_id)
        applyer = apply.create_by
        profile = Profile.objects.get(owner=applyer)
        extra_apply = ExtraApply.objects.filter(apply=apply)
        pics = extra_apply[0].extra_pic.split(",") if len(extra_apply) == 1 else []
        page = render_to_response('review/modal_promotion.html',
                                  {"apply": apply, "user": applyer, "profile": profile, 'oss_url': settings.OSS_URL,
                                   "pics": pics},
                                  context_instance=RequestContext(request))
        return page


# 查看额度提升 modal
@page_permission(check_employee)
def view_promote_info_view(request, apply_id):
    if request.method == 'GET':
        apply = Apply.objects.get(pk=apply_id)
        applyer = apply.create_by
        profile = Profile.objects.get(owner=applyer)
        reviews = Review.objects.filter(order=apply).order_by("-id")
        review = reviews[0] if len(reviews) > 0 else None
        extra_apply = ExtraApply.objects.filter(apply=apply)
        pics = extra_apply[0].extra_pic.split(",") if len(extra_apply) == 1 else []
        page = render_to_response('review/view_modal_promotion.html',
                                  {"apply": apply, "user": applyer, "profile": profile, 'oss_url': settings.OSS_URL,
                                   'review': review,
                                   "pics": pics},
                                  context_instance=RequestContext(request))
        return page


def __report_review_data(apply_obj, username):
    workflow_obj = WorkFlow.objects.get(id=apply_obj.workflow_id)
    workstatus_obj = WorkStatus.objects.get(Q(workflow_id=apply_obj.workflow_id) & Q(status_code=apply_obj.status))
    statusflow_id = StatusFlow.objects.get(Q(status_id =workstatus_obj.id) & Q(flow_id=workflow_obj.id)).status_id
    index = list(StatusFlow.objects.filter(flow_id=workflow_obj.id).order_by('id').values_list('status_id', flat = True)).index(statusflow_id)
    org_account, service_id = __get_data_server_params(apply_obj.platform, apply_obj.product)
    data = {
            "measurement":"review_assignment",
            "time":int(time.time()*10**9),
            "tags":{
                "org_account":org_account,
                "reviewer":username,
                "apply_type":str(index)
                },
            "fields":{
                "apply_id": str(apply_obj.id)
                }
            }
    result = data_report_client.report_data(json.dumps(data, ensure_ascii=False))
    Log().info('__report_review_data, data:{0} result{1}'.format(data, result))

@page_permission(check_employee)
@csrf_exempt
def add_review(request):
    if request.method == 'POST':
        try:
            apply_id = request.POST.get("apply_id")
            staff = Employee.objects.get(user=request.user)
            apply_obj = Apply.objects.get(pk=apply_id)
            if apply_obj.status in ['y', 'n', 'r']:
                if int(apply_obj.owner_id) ==  int(staff.id):
                    return HttpResponse(json.dumps({'code': 1, 'msg': ''}))
                else:
                    return HttpResponse(json.dumps({'code': -1, 'msg': u'订单已完成审批流程'}))
            #判断审批人是否有权限打开该订单
            check_result = __check_permission(request, apply_obj)
            if check_result:
                return check_result
            else:
                reviews = Review.objects.filter(Q(order = apply_obj) & Q(review_res__in = ['0', apply_obj.status]) & Q(finish_time__isnull=True)).order_by("-id")
                # reviews = Review.objects.filter(order = apply_obj).order_by("-id")
                if len(reviews) > 0:
                    # status = apply_obj.status
                    print reviews[0].reviewer, request.user
                    if reviews[0].reviewer != staff:
                        return HttpResponse(json.dumps({'code':-1, 'msg': u"%s审批中" % reviews[0].reviewer.username}))
                    elif reviews[0].reviewer == staff:
                        review = reviews[0]
                        review.save()
                        apply_obj.owner_id = staff.id
                        apply_obj.save()
                        return HttpResponse(json.dumps({'code': 1, 'msg': u'不能重复抢单'}))
                elif len(reviews) == 0:  # 没有review 新建
                    if apply_obj.status in ['y', 'n', 'r']:
                        return HttpResponse(json.dumps({'code': 1, 'msg': u'不允许重复抢单'}))
                    if apply_obj.status not in ('n', 'r', 'y'):
                        reviews = Review.objects.filter(Q(order = apply_obj) & Q(review_res = apply_obj.status) & Q(finish_time__isnull=True)).order_by("-id")
                        if reviews.count() == 0 :
                            __report_review_data(apply_obj, request.user.username)
                    review = Review()
                    review.reviewer = staff
                    review.create_at = datetime.now()
                    review.order = apply_obj
                    review.review_res = apply_obj.status
                    review.status = 0
                    review.save()
                    apply_obj.owner_id = staff.id
                    apply_obj.save()
                # 如果订单分配到组或在待审核阶段还没有人抢到该单时，则抢到后改变订单的owner_type为个人
                if apply_obj.owner_type == 1 or apply_obj.owner_type == None:
                    apply_obj.owner_type = 0
                    apply_obj.owner_id = staff.id
                    apply_obj.save()
        except Exception, e:
            traceback.print_exc()
            return HttpResponse(json.dumps({'code':-1, 'msg':e.message}))
        return HttpResponse(json.dumps({"code": 0, 'msg': ''}))
    return HttpResponse(json.dumps({"error": u"post only"}))

def _auto_add_review(apply_obj, employee_id):
    try:
        staff = Employee.objects.get(pk = employee_id)

        __report_review_data(apply_obj, staff.user.username)
        new_review = Review()
        new_review.reviewer = staff
        new_review.create_at = datetime.now()
        new_review.order = apply_obj
        new_review.review_res = apply_obj.status
        new_review.status = 0
        new_review.save()
        # 如果订单分配到组或在待审核阶段还没有人抢到该单时，则抢到后改变订单的owner_type为个人
        #if apply_obj.owner_type == 1 or apply_obj.owner_type == None:
        #    apply_obj.owner_type = 0
        #    apply_obj.owner_id = staff.id
        #    apply_obj.save()
    except Exception, e:
        traceback.print_exc()
        return HttpResponse(json.dumps({'code':-1, 'msg':e.message}))
    return HttpResponse(json.dumps({"code": 0, 'msg': ''}))

@csrf_exempt
def re_apply_add_review(request):
    print 're_apply_add_review:', request
    if request.method == 'POST':
        try:
            apply_id = request.POST.get("apply_id")
            apply_obj = Apply.objects.get(pk=apply_id)

            review = Review.objects.filter(Q(order = apply_obj) & Q(finish_time__isnull=False)).order_by("-id").first()
            if review:
                __report_review_data(apply_obj, review.reviewer.user.username)
                new_review = Review()
                new_review.reviewer = review.reviewer
                new_review.create_at = datetime.now()
                new_review.order = apply_obj
                new_review.review_res = apply_obj.status
                new_review.status = 0
                new_review.save()
            # 如果订单分配到组或在待审核阶段还没有人抢到该单时，则抢到后改变订单的owner_type为个人
            #if apply_obj.owner_type == 1 or apply_obj.owner_type == None:
            #    apply_obj.owner_type = 0
            #    apply_obj.owner_id = staff.id
            #    apply_obj.save()

        except Exception, e:
            traceback.print_exc()
            return HttpResponse(json.dumps({'code':-1, 'msg':e.message}))
        return HttpResponse(json.dumps({"code": 0, 'msg': ''}))
    return HttpResponse(json.dumps({"error": u"post only"}))


def _make_snapshot_apply(request, apply_object, user_dict=None):
    return 
    try:
        table = mongo_client['snapshot']['basic_apply']
        snapshot_data = table.find_one({"apply_info.id": apply_object.id})
        profiles = Profile.objects.filter(owner=apply_object.create_by)
        if not user_dict:
            user_dict = _get_user_info(request, apply_object.create_by)
            review_dict = _get_interface_data(request, apply_object.create_by)
            user_dict.update(review_dict)
        # if 'callrecord' in user_dict:
        #     snapshot_callrecord = json.loads(serializers.serialize('json', user_dict['callrecord']))
        # else:
        #     snapshot_callrecord = []
        # callrecord_doc = [i['fields'] for i in snapshot_callrecord]
        if 'addressbooks' in user_dict:
            snap_addressbook = json.loads(serializers.serialize('json', user_dict['addressbooks']))
        else:
            snap_addressbook = []
        addressbook_doc = [i['fields'] for i in snap_addressbook]
        apply_data = json.loads(serializers.serialize('json', [apply_object, ]))[0]
        snap_bankcards = json.loads(serializers.serialize('json', user_dict['bankcards']))
        bankcards_doc = [i['fields'] for i in snap_bankcards]
        snap_chsis = json.loads(serializers.serialize('json', user_dict['chsis']))
        chsis_doc = [i['fields'] for i in snap_chsis]
        contacts_objects = []
        for contact in user_dict['contacts']:
            snap_contact = json.loads(serializers.serialize('json', [contact[0], ]))[0]
            contact_doc = snap_contact['fields']
            contacts_objects.append((contact_doc, contact[1]))
        idcards = IdCard.objects.filter(owner=apply_object.create_by)
        idcard_doc = {}
        if len(idcards):
            idcard_doc = json.loads(serializers.serialize('json', idcards))[0]['fields']
        check_status = user_dict['check_status']
        check_status_doc = json.loads(serializers.serialize('json', [check_status, ]))[0]['fields']
        profiles_doc = {}
        if profiles:
            profiles_data = json.loads(serializers.serialize('json', profiles))[0]
            profiles_doc = profiles_data['fields']
            profiles_doc['id'] = profiles_data['pk']
        user_data = json.loads(serializers.serialize('json', [apply_object.create_by, ]))[0]
        user_doc = user_data['fields']
        user_doc['id'] = user_data['pk']
        chsi_auths = Chsiauthinfo.objects.filter(user_id=apply_object.create_by.id)
        chsi_auth = chsi_auths[0] if len(chsi_auths) == 1 else None
        chsi_data = {}
        if chsi_auth:
            if chsi_auth.username:
                try:
                    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_KEY)
                    chsi_auth.username = cipher.decrypt(base64.b64decode(chsi_auth.username.strip('\0')))
                except:
                    chsi_auth.username = ''
            chsi_data = json.loads(serializers.serialize('json', [chsi_auth, ]))[0]['fields']
        data = {'apply_info': apply_data['fields'], "user_info": user_doc,
                'chsi_auth': chsi_data, 'addressbook': addressbook_doc, "bankcards": bankcards_doc,
                'chsis': chsis_doc, 'contacts': contacts_objects}
        data['user_info'].update({'profile': profiles_doc, "id_card_info": idcard_doc,
                                  "check_status": check_status_doc})
        data["apply_info"].update({"id": apply_data['pk']})
        has_new_data = None
        try:
            has_new_data = redis_client.hget("USER_INFO:%d" % apply_object.id, "mobile_record")
        except Exception, e:
            Log().error(u"_make_snapshot_apply call redis error")
            has_new_data = False
        profile = profiles[0] if len(profiles) == 1 else None
        if profile.job == 2:
            data['has_ebusiness'] = True
        else:
            data['has_ebusiness'] = False
        if not snapshot_data or has_new_data or 'has_ebusiness' not in snapshot_data:
            data["new_data"] = True
            basic_data = data_query.basic_data.copy()
            basic_data["user_id"] = apply_object.create_by.id
            phone_basics = data_query.get_phonebasic_data(basic_data)
            data["phone_basics"] = phone_basics
            phone_data = data_query.phone_data.copy()
            phone_data["user_id"] = apply_object.create_by.id
            phone_data["contact"] = []
            for contact, names in user_dict['contacts']:
                phone_data["contact"].append({"contact_name": contact.name, "contact_type": contact.relationship,
                                              "contact_tel": contact.phone_no})
            contact_phone_calls, contact_phone_call_columns = data_query.get_phonecall_data(phone_data)
            contact_phone_data = None
            if contact_phone_calls:
                contact_phone_data = []
                for featrue in contact_phone_calls:
                    name_inaddressbook = AddressBook.objects.filter(owner=apply_object.create_by,
                                                                    phone_number=featrue[0])
                    contact_name = name_inaddressbook[0].name if name_inaddressbook else ''
                    contact_phone_data.append((featrue, contact_name,))
            data["contact_phone_call_columns"] = contact_phone_call_columns
            data["contact_phone_calls"] = contact_phone_data
            corp_data = data_query.corp_data.copy()
            corp_data["user_id"] = apply_object.create_by.id
            (corp_contact_phone_calls, corp_contact_phone_call_columns) = data_query.get_corp_phonecall_data(corp_data)
            data["corp_contact_phone_call_columns"] = corp_contact_phone_call_columns
            data["corp_contact_phone_calls"] = corp_contact_phone_calls
            ebusiness_data = data_query.ebusiness_data.copy()
            ebusiness_data["user_id"] = apply_object.create_by.id
            e_business = data_query.get_ebusiness_data(ebusiness_data)
            data["e_business"] = e_business
            deliver_data = data_query.deliver_data.copy()
            deliver_data["user_id"] = apply_object.create_by.id
            e_deliver = data_query.get_deliver_data(deliver_data)
            data["e_deliver"] = e_deliver
            phone_location_data = data_query.phone_location_data.copy()
            phone_location_data["user_id"] = apply_object.create_by.id
            phone_location = data_query.get_phone_location_data(phone_location_data)
            data["phone_location"] = phone_location
        if snapshot_data:
            object_id = table.find_one_and_update({"apply_info.id": apply_object.id}, {"$set": data})
            Log().debug("business_manager snapshot update apply data: %s" % object_id)
        else:
            object_id = table.insert(data)
            Log().info('mongo insert ObjectId(%s)' % object_id)
    except:
        traceback.print_exc()
        Log().error("_make_snapshot_apply mongo error:%s" % traceback.format_exc())


def _read_snapshot_apply(request, apply_id):
    start = time.time()
    Log().debug('start read snapshot:%s' % start)
    apply_info = Apply.objects.get(pk=apply_id)
    apply_dict = _get_review_info(request, apply_info)
    try:
        table = mongo_client['snapshot']['basic_apply']
        snapshot_data = table.find_one({"apply_info.id": apply_info.id})
        Log().info('mongo data: %s' % snapshot_data)
        profiles = Profile.objects.filter(owner=apply_info.create_by)
        profiles_keys = Profile._meta.get_all_field_names()
        profiles_keys.pop(profiles_keys.index('owner_id'))
        chsi_auths = Chsiauthinfo.objects.filter(user_id=apply_info.create_by.id)
        chsi_auth = chsi_auths[0] if len(chsi_auths) == 1 else None
        chsi_data = {}
        if chsi_auth:
            if chsi_auth.username:
                try:
                    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_KEY)
                    chsi_auth.username = cipher.decrypt(base64.b64decode(chsi_auth.username.strip('\0')))
                except:
                    chsi_auth.username = ''
            chsi_data = json.loads(serializers.serialize('json', [chsi_auth, ]))[0]['fields']
        snapshot_profile_keys = []
        if not snapshot_data:
            user_dict = _get_user_info(request, apply_info.create_by)
            all_dict = user_dict.copy()
            all_dict.update(apply_dict)
            _make_snapshot_apply(request, apply_info, user_dict)
            return all_dict
        else:
            if 'user_info' in snapshot_data:
                user_snap = snapshot_data['user_info'].copy()
                if 'check_status' in user_snap:
                    user_snap.pop('check_status')
                if 'profile' in user_snap:
                    user_snap.pop('profile')
                if 'id_card_info' in user_snap:
                    user_snap.pop('id_card_info')
                if 'invitation' in user_snap:
                    user_snap.pop('invitation')
                user_object = User(**user_snap)
                if 'profile' in snapshot_data['user_info']:
                    snapshot_profile_keys = snapshot_data['user_info']['profile'].keys()
            else:
                user_object = apply_info.create_by
                user_data = json.loads(serializers.serialize('json', [apply_info.create_by, ]))[0]
                user_doc = user_data['fields']
                user_doc['id'] = user_data['pk']
                table.find_one_and_update({"apply_info.id": apply_info.id}, {"$set": {'user_info': user_doc}})
            diff_keys = set(snapshot_profile_keys) ^ set(profiles_keys) if profiles_keys else set(snapshot_profile_keys)

            if "owner" in diff_keys:
                diff_keys.remove("owner")
            if diff_keys:
                for key in diff_keys:
                    data_key = 'user_info.profile.%s' % key
                    update_key = "profiles[0].%s" % key
                    if key == 'owner':
                        update_key = apply_info.create_by_id
                        table.find_one_and_update({"apply_info.id": apply_info.id}, {"$set": {data_key: update_key}})
                    else:
                        table.find_one_and_update({"apply_info.id": apply_info.id},
                                                  {"$set": {data_key: eval(update_key)}})
            if 'chsi_auth' in snapshot_data:
                chsi_auth = Chsiauthinfo(**snapshot_data['chsi_auth'])
            else:
                data_key = 'chsi_auth'
                table.find_one_and_update({"apply_info.id": apply_info.id}, {"$set": {data_key: chsi_data}})
            addressbook_objects = []
            if 'addressbook' in snapshot_data:
                snapshot_data['addressbook'] = [data for data in snapshot_data['addressbook'] if data != 'None']
                if len(snapshot_data['addressbook']) <= 10:
                    addresses_sum = AddressBook.objects.filter(owner=apply_info.create_by).order_by('id')
                    if len(addresses_sum) > 10:
                        snap_addressbook = json.loads(serializers.serialize('json', addresses_sum))
                        snap_data = [i['fields'] for i in snap_addressbook]
                        table.find_one_and_update({"apply_info.id": apply_info.id},
                                                  {"$set": {'addressbook': snap_data}})
                        addressbook_objects = addresses_sum[:10]
                    else:
                        for data in snapshot_data['addressbook']:
                            data.pop('owner')
                            addressbook_objects.append(AddressBook(owner=apply_info.create_by, **data))
                        addressbook_objects = addressbook_objects[:10]
            else:
                Log().info('no addressbook:%s' % apply_info.create_by)
                addresses_sum = AddressBook.objects.filter(owner=apply_info.create_by).order_by('id')
                snap_addressbook = json.loads(serializers.serialize('json', addresses_sum))
                snap_data = [i['fields'] for i in snap_addressbook]
                table.find_one_and_update({"apply_info.id": apply_info.id}, {"$set": {'addressbook': snap_data}})
                addressbook_objects = addresses_sum[:10]
            bankcards_objects = []
            if 'bankcards' in snapshot_data:
                for data in snapshot_data['bankcards']:
                    data.pop('user')
                    bankcards_objects.append(BankCard(**data))
            else:
                user_info = _get_user_info(request, apply_info.create_by)
                snap_bankcards = json.loads(serializers.serialize('json', user_info['bankcards']))
                snap_data = [i['fields'] for i in snap_bankcards]
                table.find_one_and_update({"apply_info.id": apply_info.id}, {"$set": {'bankcards': snap_data}})
                bankcards_objects = user_info['bankcards']
            chsis_objects = []
            if 'chsis' in snapshot_data:
                for data in snapshot_data['chsis']:
                    data.pop('user')
                    chsis_objects.append(Chsi(user=apply_info.create_by, **data))
            else:
                user_info = _get_user_info(request, apply_info.create_by)
                snap_chsis = json.loads(serializers.serialize('json', user_info['chsis']))
                chsis_doc = [i['fields'] for i in snap_chsis]
                table.find_one_and_update({"apply_info.id": apply_info.id}, {"$set": {'chsis': chsis_doc}})
                chsis_objects = user_info['chsis']
            contacts_objects = []
            if 'contacts' in snapshot_data:
                snapshot_data['contacts'] = [data for data in snapshot_data['contacts'] if data[0]['name'] != 'None']
                for data in snapshot_data['contacts']:
                    data[0].pop('owner')
                    same_ids = ContactInfo.objects.filter(
                        Q(phone_no=data[0]['phone_no']) & ~Q(owner=apply_info.create_by))
                    contact = ContactInfo(owner=apply_info.create_by, **data[0])
                    contact.contact_repeat = len(same_ids)
                    contact.contacts = same_ids[:10]
                    contacts_objects.append((contact, data[1]))
            else:
                user_info = _get_user_info(request, apply_info.create_by)
                for contact, names in user_info['contacts']:
                    snap_contact = json.loads(serializers.serialize('json', [contact, ]))[0]
                    contact_doc = snap_contact['fields']
                    contacts_objects.append((contact_doc, names,))
                table.find_one_and_update({"apply_info.id": apply_info.id}, {"$set": {'contacts': contacts_objects}})
                contacts_objects = user_info['contacts']
            if 'profile' in snapshot_data['user_info']:
                profile_doc = snapshot_data['user_info']['profile']
                if "owner" in profile_doc:
                    profile_doc.pop("owner")
                profile_object = Profile(owner=apply_info.create_by, **profile_doc)
            else:
                profiles = Profile.objects.filter(owner=apply_info.create_by)
                profile_object = profiles
            id_card_doc = {}
            if snapshot_data['user_info'].get('id_card_info', None):
                id_card_doc = snapshot_data['user_info']['id_card_info']
                if 'owner' in id_card_doc:
                    id_card_doc.pop('owner')
            idcard_object = IdCard(owner=apply_info.create_by, **id_card_doc)
            same_ids = User.objects.filter(device_id=apply_info.create_by.device_id)
            device_id_repeat = len(same_ids)
            ids = same_ids[:10]
            try:
                register_ip = redis_client.hget("USER_INFO:%d" % apply_info.create_by.id, "ip")
            except:
                Log().error(u"_read_snapshot_apply call redis error")
                register_ip = ''
            check_status_data = snapshot_data['user_info']['check_status']
            if check_status_data:
                if 'owner' in check_status_data:
                    check_status_data.pop("owner")
                check_status_object = CheckStatus(owner=apply_info.create_by, **check_status_data)
            else:
                check_status_object = None
            user_dict = {}
            profile = profiles[0] if len(profiles) == 1 else None
            if profile.job == 2:
                user_dict["has_ebusiness"] = True
            else:
                user_dict["has_ebusiness"] = False
            has_new_data = None
            if 'has_ebusiness' in snapshot_data:
                has_ebusiness = snapshot_data['has_ebusiness']
            else:
                has_ebusiness = user_dict['has_ebusiness']
            try:
                has_new_data = redis_client.hget("USER_INFO:%d" % apply_info.create_by_id, "mobile_record")
            except Exception, e:
                Log().error(u"_read_snapshot_apply call redis error")
            if has_new_data and settings.USE_DATA_SERVER:
                user_dict["new_data"] = True
                basic_data = data_query.basic_data.copy()
                basic_data["user_id"] = apply_info.create_by.id
                phone_basics = data_query.get_phonebasic_data(basic_data)
                user_dict["phone_basics"] = phone_basics
                phone_data = data_query.phone_data.copy()
                phone_data["user_id"] = apply_info.create_by.id
                phone_data["contact"] = []
                for contact, names in contacts_objects:
                    phone_data["contact"].append({"contact_name": contact.name, "contact_type": contact.relationship,
                                                  "contact_tel": contact.phone_no})
                contact_phone_calls, contact_phone_call_columns = data_query.get_phonecall_data(phone_data)
                contact_phone_data = None
                if contact_phone_calls:
                    contact_phone_data = []
                    for phone_call, featrue in contact_phone_calls:
                        if phone_call:
                            name_inaddressbook = AddressBook.objects.filter(owner=apply_info.create_by,
                                                                            phone_number=phone_call)
                            contact_name = name_inaddressbook[0].name if name_inaddressbook else ''
                            contact_phone_data.append((phone_call, featrue, contact_name,))
                user_dict["contact_phone_call_columns"] = contact_phone_call_columns
                user_dict["contact_phone_calls"] = contact_phone_data
                corp_data = data_query.corp_data.copy()
                corp_data["user_id"] = apply_info.create_by.id
                (corp_contact_phone_calls, corp_contact_phone_call_columns) = data_query.get_corp_phonecall_data(
                    corp_data)
                user_dict["corp_contact_phone_call_columns"] = corp_contact_phone_call_columns
                user_dict["corp_contact_phone_calls"] = corp_contact_phone_calls
                ebusiness_data = data_query.ebusiness_data.copy()
                ebusiness_data["user_id"] = apply_info.create_by.id
                e_business = data_query.get_ebusiness_data(ebusiness_data)
                user_dict["e_business"] = e_business
                deliver_data = data_query.deliver_data.copy()
                deliver_data["user_id"] = apply_info.create_by.id
                e_deliver = data_query.get_deliver_data(deliver_data)
                user_dict["e_deliver"] = e_deliver
                phone_location_data = data_query.phone_location_data.copy()
                phone_location_data["user_id"] = apply_info.create_by.id
                phone_location = data_query.get_phone_location_data(phone_location_data)
                user_dict["phone_location"] = phone_location
                table.find_one_and_update({"apply_info.id": apply_info.id}, {"$set": user_dict})
                Log().debug('end make and  read snapshot:%s' % time.time())
            else:
                user_dict["new_data"] = False
                call = CallRecord.objects.filter(owner=apply_info.create_by).order_by('-duration')[:10]
                user_dict['callrecord'] = call
                user_dict["phone_basics"] = snapshot_data['phone_basics']
                user_dict["contact_phone_call_columns"] = snapshot_data["contact_phone_call_columns"]
                if snapshot_data["contact_phone_calls"]:
                    snapshot_data["contact_phone_calls"] = [data for data in snapshot_data["contact_phone_calls"] if
                                                            data[0] != 'None']
                user_dict["contact_phone_calls"] = snapshot_data["contact_phone_calls"]
                user_dict["corp_contact_phone_call_columns"] = snapshot_data["corp_contact_phone_call_columns"]
                user_dict["corp_contact_phone_calls"] = snapshot_data["corp_contact_phone_calls"]
                user_dict["e_business"] = snapshot_data["e_business"]
                user_dict["e_deliver"] = snapshot_data["e_deliver"]
                user_dict["phone_location"] = snapshot_data["phone_location"]
                Log().debug('end read snapshot:%s' % time.time())
            update_dict = {"user": user_object, 'profile': profile_object, 'idcard': idcard_object,
                           'device_id_repeat': device_id_repeat, 'has_ebusiness': has_ebusiness,
                           'register_ip': register_ip, "ip_address": "",
                           'oss_url': settings.OSS_URL, 'chsi_auth': chsi_auth, 'check_status': check_status_object,
                           'addressbook': addressbook_objects, 'ids': ids, 'bankcards': bankcards_objects,
                           'chsis': chsis_objects, 'contacts': contacts_objects}
            user_dict.update(update_dict)
            all_dict = user_dict.copy()
            all_dict.update(apply_dict)
            end = time.time()
            Log().debug("read snapshot consumed time:%s" % (end - start))
            return all_dict
    except:
        Log().error('_read_snapshot_apply %s' % traceback.format_exc())
        traceback.print_exc()
        user_dict = _get_user_info(request, apply_info.create_by)
        all_dict = user_dict.copy()
        all_dict.update(apply_dict)
        return all_dict


def __get_statusflow_by_apply(apply_obj):
    workflow = WorkFlow.objects.get(id=apply_obj.workflow_id)

    status_query = Q(status_code = apply_obj.status)
    workflow_query = Q(workflow_id = apply_obj.workflow_id)
    workstatus_obj = WorkStatus.objects.get(status_query & workflow_query) #根据工作流和当前状态查找状态机记录

    #获取流程配置信息
    flow_id_query = Q(flow_id = apply_obj.workflow_id)
    status_id_query = Q(status_id = workstatus_obj.id)
    statusflow_obj = StatusFlow.objects.get(flow_id_query & status_id_query)
    return statusflow_obj

def go_to_next(request):
    if request.method == 'GET':
        apply_id = request.GET.get('apply_id')
        apply_obj = Apply.objects.get(id=apply_id)
        statusflow_obj = __get_statusflow_by_apply(apply_obj)
        if statusflow_obj.template_id:
            return HttpResponse(json.dumps({'template_id':template_id}))
        else:
            return HttpResponse(json.dumps({'template_id':''}))


def __report_finish_data(request, apply_obj, is_pass=u'通过', has_reviewer=True, is_final=False, spend_time_s = 0):
    org_account, service_id = __get_data_server_params(apply_obj.platform, apply_obj.product)
    default_data = {
            'measurement':'apply_review',
            'time':int(time.time()*10**9),
            'tags':{
                'org_account':org_account,
                'reviewer':request.user.username if has_reviewer else '',
                'review_result':is_pass,
                'address':'',
                'channel':'',
                'salesman':apply_obj.salesman,
                'invite_code':'',
                'education':'',
                'user_type':'',
                'apply_type':'',
                'age':''
                },
            'fields':{
                'apply_id':str(apply_obj.id),
                'review_spend_time':spend_time_s
                }
            }

    try:
        if not is_final:
            workflow_obj = WorkFlow.objects.get(id=apply_obj.workflow_id)
            workstatus_obj = WorkStatus.objects.get(Q(workflow_id=apply_obj.workflow_id) & Q(status_code=apply_obj.status))
            statusflow_id = StatusFlow.objects.get(Q(status_id =workstatus_obj.id) & Q(flow_id=workflow_obj.id)).status_id
            index = list(StatusFlow.objects.filter(flow_id=workflow_obj.id).order_by('id').values_list('status_id', flat = True)).index(statusflow_id)
            default_data['tags']['apply_type'] = str(index)
        else:
            default_data['tags']['apply_type'] = '-1'
            default_data['tags']['reviewer'] = ''
            traceback.print_exc()

        send_result = user_center_client.get_user_info(apply_obj.create_by_id)
        user = json.loads(send_result.user_info)
        if user.get("chsi_info"):
            default_data["tags"]["education"] = user["chsi_info"][0].get("education")
        if user.get("id_no"):
            default_data["tags"]["age"] = str(int(datetime.now().year) - int(user["id_no"][6:10]))
        if user.get("channel"):
            default_data["tags"]["channel"] = user["channel"].decode('utf-8')
        if user.get("profile_info"):
            profile_info = user["profile_info"]
            if profile_info.get("int32_is_student"):
                default_data["tags"]["user_type"] = u"学生" if profile_info["int32_is_student"] else u"工薪"
            if profile_info.get("string_company_address"):
                default_data["tags"]["address"] = profile_info["string_company_address"].split('#')[0].decode('utf-8')
        data_report_client.report_data(json.dumps(default_data))
    except Exception,e:
        Log().error('__report_finish_data failed, applyid:{0} error:{1}'.format(apply_obj.id, e))


def __new_order(apply_obj):
    user = apply_obj.create_by
    bank_id = BankCard.objects.get(owner=user).id
    order_number = "%s%d" %(datetime.now().strftime('%y%j%H%M%S'), user.id)
    rsp = risk_client.new_repayment(user.id, apply_obj.amount, apply_obj.strategy_id, '', 
                                    bank_id, order_number, apply_obj.platform, apply_obj.product)
    if rsp.status in [0, 1, 5]:
        apply_obj.repayment = RepaymentInfo.objects.get(id=rsp.repayment_id)
        apply_obj.save()
    else:
        apply_obj.status = '3'
        return HttpResponse(json.dumps({'result':'创建还款记录失败'}))

@csrf_exempt
def finish_review(request):
    if request.method == 'POST':
        try:
            apply_id = request.POST.get("apply_id")
            result = request.POST.get("result")
            note_info = request.POST.get("note_info")  #审批备注信息
            owner_type = request.POST.get("owner_type")
            owner_id = request.POST.get("owner_id")
            comment = request.POST.get('comment')
            staff = Employee.objects.get(user=request.user)

            if result not in ['y', 'n', 'r']:  #如果结果为通过、打回、拒绝则不检查是否指定流转人
                if not (owner_type and owner_id):
                    return HttpResponse(__return_json(is_right=False, msg='请指定流转人。'))

            apply_obj = Apply.objects.get(id=apply_id)
            check_status = CheckStatus.objects.get(owner=apply_obj.create_by)

            if apply_obj.status in ['y']:
                return HttpResponse(__return_json(is_right=False, msg='订单已通过。'))

            is_pass = ''
            if result == 'next' or result == 'y':
                is_pass = '通过'
            elif result == 'r':
                is_pass = '打回修改'
            elif result == 'n':
                is_pass = '拒绝'

            statusflow_obj = __get_statusflow_by_apply(apply_obj)
            review = Review.objects.filter(order=apply_obj).order_by('-create_at').first()

            # 上报本次审批操作
            this_review_time = (datetime.now() - review.create_at).seconds
            __report_finish_data(request, apply_obj, is_pass=is_pass, has_reviewer=True, spend_time_s = this_review_time)

            #根据流程配置信息获取下个状态的状态码
            if statusflow_obj.next_status_id == -1:
                next_status = WorkStatus.objects.get(Q(workflow_id=apply_obj.workflow_id) & Q(status_code='y')).status_code
            else:
                next_status = WorkStatus.objects.get(id=statusflow_obj.next_status_id).status_code
            review_record = ReviewRecord(review=review)
            if result == 'next':    #如果通过，则保存apply的下个状态
                if apply_obj.create_by.is_register < 0:
                    Log().info("用户已注销")
                    apply_obj.status = 'e'  # 取消订单/
                    apply_obj.save()
                    return HttpResponse(json.dumps({"result": u"ok"}))
                check_status.set_profile_status('waiting')
            elif result in ('n', 'r',):
                next_status = result
                if result == 'n':
                    check_status.set_profile_status('deny')
                else:
                    check_status.set_profile_status('recheck')
            elif result == 'y':
                check_status.set_profile_status('pass')
            review_record.review_status = next_status
            review_record.review_note = note_info
            review_record.review_message = comment
            review_record.save()
            review.finish_time = datetime.now()
            review.review_res = next_status
            review.reviewer = staff
            review.review_res = next_status
            apply_obj.status = next_status
            apply_obj.finish_time = datetime.now()
            apply_obj.owner_type = owner_type
            apply_obj.owner_id = owner_id
            apply_obj.comment = comment
            
            if result in ['y', 'n', 'r']:
                apply_obj.owner_type = 0
                apply_obj.owner_id = staff.id
                apply_obj.save()

            #如果审批通过，而且不是现金贷，就生成贷款信息
            if result == 'y' and apply_obj.strategy_id != 0 and apply_obj.amount != 0:
                new_order_result = __new_order(apply_obj)
                if new_order_result:
                    return new_order_result
            if result == 'r': #谁打回，订单属于谁
                apply_obj.owner_type = 0
                apply_obj.owner_id = staff.id

            apply_obj.save()
            review.save()

            total_review_time = (review.finish_time - apply_obj.create_at).seconds
            # 流转上报，在打回修改、拒绝、全流程通过的三种状态下要求上报两次
            if result == 'y':
                __report_finish_data(request, apply_obj, is_pass=is_pass, has_reviewer=True, is_final=True, spend_time_s = total_review_time)
            elif result == 'r':
                __report_finish_data(request, apply_obj, is_pass=is_pass, has_reviewer=True, is_final=True, spend_time_s = total_review_time)
            elif result == 'n':
                __report_finish_data(request, apply_obj, is_pass=is_pass, has_reviewer=True, is_final=True, spend_time_s = total_review_time)

            if result == 'next' and owner_type == '0':
                print 'next auto add review owner_id:', owner_id
                _auto_add_review(apply_obj, owner_id)

            return HttpResponse(json.dumps({"code": 0, 'msg':''}))

        except Exception as e:
            traceback.print_exc()
            return HttpResponse(json.dumps({"code": -1, 'msg':e.message}))



        # try:
            # # employer = Employee.objects.get(user=request.user)
            # # post = employer.post
            # # apply_obj = Apply.objects.get(pk=apply_id)
            # # current_status = apply_obj.status

            # # review = Review.objects.get(pk=review_id)
            # review = Review.objects.filter(order=apply_obj).order_by('-create_at').first()
            # staff = Employee.objects.get(user=request.user)
            # Log().info(u"%s submit finish_review: %d)%s %s" % (
            # staff.username, review.order.id, review.order.create_by.name, review.order.create_by.phone_no))
            # if apply_obj.create_by.is_register < 0:
                # Log().info("用户已注销")
                # apply_obj.status = 'e'  # 取消订单
                # apply_obj.save()
                # return HttpResponse(json.dumps({"result": u"ok"}))
            # # print 'current status'*30
            # # print current_status
            # # if current_status == '0':
                # # status = '1'
            # # elif current_status == '1':
                # # status = '2'
            # # elif current_status == '2':
                # # status = '3'
            # # elif current_status == '3':
                # # status = 'y'
            # status = next_status
            # # for area_type in ("id", "family", "chsi", "e_business",  "pic_front", "o_pic_back", "q_pic_hand", "work", "c_interview_review"):
            # for area_type in ("c_interview", ):

                # review_record = ReviewRecord(review=review)
                # review_record.review_status = request.POST.get(area_type + "_review_radio")
                # if status == 'y':
                # # if status in ['0','1','2','3','y' ]:
                    # if review_record.review_status != 'y':
                        # status = review_record.review_status
                # elif status == 'r':
                    # if review_record.review_status == 'n':
                        # status = review_record.review_status
                # # if area_type + "_review_notes" == 'b_out_review_notes' and not current_status in ['0', 'n'] and status != 'n':
                    # # print 'in out report-*'*20
                    # # report_url = request.POST.get('b_out_review_notes').strip()
                    # # print 'report url'
                    # # print report_url
                    # # if not "http" in report_url:
                        # # report_result = get_out_page(request, apply_id)
                        # # print 'report result:'
                        # # print report_result
                        # # if not "http" in report_result:
                            # # return HttpResponse({'error': '没有上传外访报告'})
                # review_record.review_note = request.POST.get(area_type + "_review_notes")[:254] if request.POST.get(
                    # area_type + "_review_notes") else ""
                # review_record.review_message = request.POST.get(area_type + "_review_msg")[:254] if request.POST.get(
                    # area_type + "_review_msg") else ""
                # review_record.review_type = area_type[0]
                # review_record.save()
                # extra_apply = ExtraApply.objects.filter(apply=apply_obj)
                # if len(extra_apply) == 0:
                    # extra_apply = ExtraApply()
                    # extra_apply.apply = apply_obj
                # else:
                    # extra_apply = extra_apply[0]
                # if area_type == "work":
                    # extra_apply.message_1 = review_record.review_message
                # elif area_type == "id":
                    # extra_apply.message_1 = review_record.review_message
                # elif area_type == "chsi":
                    # extra_apply.message_2 = review_record.review_message
                # elif area_type == "family":
                    # extra_apply.message_3 = review_record.review_message
                # elif area_type == "pic_front":
                    # extra_apply.message_4 = review_record.review_message
                # elif area_type == "o_pic_back":
                    # extra_apply.message_5 = review_record.review_message
                # elif area_type == "q_pic_hand":
                    # extra_apply.message_6 = review_record.review_message
                # elif area_type == "b_out":
                    # extra_apply.message_7 = review_record.review_message
                # elif area_type == "third":
                    # extra_apply.message_8 = review_record.review_message
                # elif area_type == "c_interview":
                    # extra_apply.message_9 = review_record.review_message
                # extra_apply.save()
            # review_status = 1 if status not in ['y', 'r', 'n'] else 0
            # review.reviewer_done = staff
            # review.finish_time = datetime.now()
            # review.review_res = status
            # review.status = review_status
            # review.save()
            # label_list = request.POST.get("label")
            # review.set_label_list(label_list, apply_obj)
            # apply_obj.finish_time = datetime.now()
            # apply_obj.status = status
            # verify_status = review.to_apply_status()
            # apply_obj.save()
            # if verify_status != -1:
                # check_status = CheckStatus.objects.get(owner=apply_obj.create_by)
                # check_status.profile_check_status = verify_status
                # # 如果审批通过 修改额度
                # if status == 'y':
                    # check_status.set_profile_status("pass")
                    # if apply_obj.create_by.channel == u"线下导入":
                        # check_status.credit_limit = 200000
                        # check_status.base_credit = 200000
                        # check_status.max_credit = 680000
                        # check_status.credit_score = 500
                    # else:
                        # pass
                    # check_status.set_profile_status("pass")
                    # try:
                        # # limit_msg_id = push_client_object.add_message(apply.create_by.id, 30)
                        # if apply_obj.type == '0':

                            # user = apply_obj.create_by
                            # bank_id = BankCard.objects.get(owner=user).id
                            # client = OrderClient(settings.RISK_SERVER['HOST'], settings.RISK_SERVER['PORT'])
                            # order_number = "%s%d" %(datetime.now().strftime('%Y%m%d%H%M%S%f'), user.id)
                            # rsp = client.new_repayment(user.id, apply_obj.amount, apply_obj.strategy_id, '', bank_id, order_number)
                            # if rsp.status in [1, 5]:
                                # # Apply.objects.get(pk=apply_id).update(repayment=rsp.repayment_id)
                                # apply_obj.repayment = RepaymentInfo.objects.get(id=rsp.repayment_id)
                                # apply_obj.save()
                                
                                # bank_ret_msg, actual_amount, bank_state_id =  try_to_get_repay_bank_amount(apply_obj, 1)
                                # if bank_state_id == 0:
                                    # msg = "error: create bank_statement fail"
                                    # Log().error(msg)
                            # else:
                                # apply_obj.status = '3'
                                # return HttpResponse(json.dumps({'result':'创建还款记录失败'}))
                    # except Exception, e:
                        # Log().error('finish_review error %s' % str(e))
                        # Log().error("finish_review push error:%s" % traceback.format_exc())
                # elif status == 'r':
                    # # 打回联系人的话需要删除反向索引
                    # check_status.set_profile_status("recheck")
                    # try:
                        # if apply_obj.type == '0':
                            # if apply_obj.create_by.wechat_openid:
                                # openid = apply_obj.create_by.wechat_openid
                                # params = {
                                    # "openid": openid,
                                    # "first": '您提交的资料还需要完善一下哦',
                                    # "name": apply_obj.create_by.name,
                                    # "phone_no": apply_obj.create_by.phone_no,
                                    # "date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                    # "remark": '快去补充资料，真实的资料能帮助您通过审核！',
                                # }
                                # url = settings.WEIXIN_PUSH_URL + 'authentication_notice'
                                # Timer(0, send_message_weixin, (params, url,)).start()
                    # except Exception, e:
                        # Log().error(str(e))
                        # Log().error("finish_review push error:%s" % traceback.format_exc())

                # elif status == 'n':
                    # check_status.set_profile_status("deny")

                # check_status.save()
            # Log().info(u"%s finish review: %d)%s  %s %s %s" % (
            # staff.username, review.order.id, review.order.create_by.name, verify_status, apply_obj.get_status_display(),
            # review.order.create_by.phone_no))
            # return HttpResponse(json.dumps({"result": u"ok"}))
        # except Exception, e:
            # Log().error(u"finish_review failed %s" % str(e))
            # traceback.print_exc()
            # return HttpResponse(json.dumps({"error": u"load failed"}))
    # return HttpResponse(json.dumps({"error": u"post only"}))


@csrf_exempt
def reset_review(request):
    if request.method == 'POST':
        apply_id = request.POST.get("apply_id")
        staff = Employee.objects.get(user=request.user)
        Log().info("%s reset review %s." % (staff.username, apply_id))
        try:
            order = Apply.objects.get(pk=apply_id)
            order.status = '0'
            order.save()
            repayments = RepaymentInfo.objects.filter(user=order.create_by)
            for repayment in repayments:
                repayment.delete()
                Log().info("reset review: delete related repayment %s." % (repayment.order_number))
            Log().info("%s reset review %s success." % (staff.username, apply_id))
            return HttpResponse(json.dumps({"result": u"ok"}))
        except Exception, e:
            Log().error(u"reset_review failed %s" % str(e))
            traceback.print_exc()
            return HttpResponse(json.dumps({"error": u"reset failed"}))
    return HttpResponse(json.dumps({"error": u"post only"}))


@csrf_exempt
def cancel_review(request):
    if request.method == 'POST':
        try:
            applyid = request.POST.get("apply_id")
            staff = Employee.objects.get(user=request.user)
            apply_obj = Apply.objects.get(pk=applyid)
            # current_status = apply_obj.status
            # apply_obj.status = status
            # apply_obj.save()
            Log().info(u"%s cancel review: %d)%s" % (staff.username, apply_obj.id, apply_obj.create_by.name))
            reviews = Review.objects.filter(order=apply_obj).order_by("id")
            if len(reviews) <= 0:
                return HttpResponse(json.dumps({"result": u"no review to cancel"}))
        except Exception, e:
            traceback.print_exc()
            return HttpResponse(json.dumps({"error": u"load failed"}))
        return HttpResponse(json.dumps({"result": "ok"}))
    return HttpResponse(json.dumps({"error": u"post only"}))


@csrf_exempt
def finish_loan_review(request):
    if request.method == 'POST':
        try:
            applyid = request.POST.get("apply_id")
            Log().info("start loan review %s" % (applyid))
            area_type = "total"
            result = request.POST.get(area_type + "_area_radio")
            apply = Apply.objects.get(pk=applyid)
            apply.status = result
            apply.finish_time = datetime.now()
            apply.save()
            # check = CheckStatus.objects.get(owner = apply.create_by)
            staff = Employee.objects.get(user=request.user)
            reviews = Review.objects.filter(order=apply)
            if len(reviews) > 0:
                review = reviews[0]
                review.reviewer_done = staff
                review.finish_time = datetime.now()
                review.review_res = 'y'
                review.save()
                review_record = ReviewRecord(review=review)
                review_record.review_status = result
                review_record.review_note = request.POST.get(area_type + "_area_notes")[:254] if request.POST.get(
                    area_type + "_area_notes") else ""
                review_record.review_message = request.POST.get(area_type + "_area_msg")[:254] if request.POST.get(
                    area_type + "_area_msg") else ""
                review_record.review_type = area_type[0]
                review_record.save()
                if result == 'n':
                    # 直接拒绝用户
                    # check.set_profile_status("deny")
                    # check.save()
                    apply.repayment.repay_status = -3
                    apply.repayment.save()
                    if apply.type != 's':
                        pass
                        # try:
                            # loan_msg_id = push_client_object.add_message(apply.create_by.id, 100008)
                            # Timer(0, push_client_object.push, (apply.create_by.id, loan_msg_id,)).start()
                            # # Timer(0, push_client_object.push, (apply.create_by.id, limit_msg_id,)).start()
                            # if apply.create_by.wechat_openid:
                                # openid = apply.create_by.wechat_openid
                                # params = {
                                    # "openid": openid,
                                    # "cash ": apply.repayment.apply_amount,
                                    # "time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                    # "status": '未审核通过',
                                # }
                                # url = settings.WEIXIN_PUSH_URL + 'latest_notice'
                                # Timer(0, send_message_weixin, (params, url,)).start()
                            # Timer(0, message_client.send_message,
                                  # (review.order.create_by.phone_no,
                                   # u"很遗憾，您提交的借贷申请被拒绝，关注花啦微信公众号：hualacash 或者直接搜索“花啦花啦”".encode("gbk"),
                                   # 5,)).start()
                            # message_client.send_message(review.order.create_by.phone_no,
                                                        # u"很遗憾，您提交的借贷申请被拒绝，如有任何疑问，请联系花啦花啦客服400-606-4728".encode("gbk"),
                                                        # 5)
                        # except Exception, e:
                            # Log().error(str(e))
                            # Log().error("finish_loan_review push error:%s" % traceback.format_exc())
                elif result == 'y':
                    apply.repayment.repay_status = 6
                    apply.repayment.save()
                    if apply.type != 's':
                        try:
                            loan_msg_id = push_client_object.add_message(apply.create_by.id, 100007)
                            Timer(0, push_client_object.push, (apply.create_by.id, loan_msg_id,)).start()
                            # Timer(0, push_client_object.push, (apply.create_by.id, limit_msg_id,)).start()
                            if apply.create_by.wechat_openid:
                                openid = apply.create_by.wechat_openid
                                params = {
                                    "openid": openid,
                                    "cash ": '恭喜，您的资料通过审核！',
                                    "time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                    "status": '审核通过',
                                }
                                url = settings.WEIXIN_PUSH_URL + 'latest_notice'
                                Timer(0, send_message_weixin, (params, url,)).start()
                            # Timer(0, message_client.send_message,
                            #       (review.order.create_by.phone_no,
                            #        u"您好，您申请的提现已成功通过审核！我们会尽快发放到您指定的银行卡，请注意查收。如有任何疑问，请联系花啦花啦客服400-606-4728".encode("gbk"),
                            #        5,)).start()
                            # message_client.send_message(review.order.create_by.phone_no,
                            #                             u"您提交的借贷申请已经通过，请登录您的花啦花啦账户签署合同。".encode("gbk"), 5)
                        except Exception, e:
                            Log().error(str(e))
                            Log().error("finish_loan_review push error:%s" % traceback.format_exc())
                else:
                    pass
                if apply.type == 's':
                    _finish_task_apply(int(applyid), staff.user.id, apply.type, result)
                Log().info("start loan review success %s. res:%s" % (applyid, result))
        except Exception, e:
            traceback.print_exc()
            Log().error("finish loan error %s" % str(e))
            return HttpResponse(json.dumps({"error": u"load failed"}))
        return HttpResponse("ok")
    return HttpResponse("only post allowed")


@csrf_exempt
def finish_promotion_review(request):
    if request.method == 'POST':
        try:
            score = request.POST.get("score")
            applyid = request.POST.get("apply_id")
            type = request.POST.get("apply_type")
            s = int(score)
            if s > 800 or s < 0:
                return HttpResponse(json.dumps({"error": u"额度超出范围"}))
            apply = Apply.objects.get(pk=applyid)
            apply.finish_time = datetime.now()
            apply.money = int(score) * 100
            apply.status = 'y'
            apply.save()
            staff = Employee.objects.get(user=request.user)
            review = Review.objects.get(order=apply)
            review.reviewer_done = staff
            review.finish_time = datetime.now()
            review.review_res = 'y'
            review.money = int(score)
            review.save()
            check = CheckStatus.objects.get(owner=apply.create_by)
            check.credit_limit += int(score) * 100
            # 微博 人人 通讯录 征信 流水 其他
            offset = int(type) - 1
            check.increase_check_status = check.increase_check_status & ~(0x3 << (2 * offset))
            check.increase_check_status = check.increase_check_status | (0x3 << (2 * offset))
            check.save()
            Log().info('incr check status %d' % check.increase_check_status)
            limit_msg_id = push_client_object.add_message(apply.create_by.id, 200011)
            Timer(0, push_client_object.push, (apply.create_by.id, limit_msg_id,)).start()
            # Timer(0, push_client_object.push, (apply.create_by.id, limit_msg_id,)).start()
            if apply.create_by.wechat_openid:
                openid = apply.create_by.wechat_openid
                params = {
                    "openid": openid,
                    "increasement": score,
                    'latest': check.credit_limit,
                    "apply_day": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "reason": '',
                }
                if apply.type == '1':
                    params['reason'] = '绑定微博账号'
                if apply.type == '7':
                    params["reason"] = "绑定京东账号"
                if apply.type == '5':
                    params['reason'] = '增加银行流水信息'
                if apply.type == '4':
                    params['reason'] = '增加征信报告信息'
                url = settings.WEIXIN_PUSH_URL + 'limitation_promote'
                Timer(0, send_message_weixin, (params, url,)).start()
            # Timer(0, message_client.send_message,
            #       (review.order.create_by.phone_no,
            #        u"您好，您申请的提现已成功通过审核！我们会尽快发放到您指定的银行卡，请注意查收。如有任何疑问，请联系花啦花啦客服400-606-4728".encode("gbk"),
            #        5,)).start()
        except Exception, e:
            Log().error("finish_promotion_review push error:%s" % traceback.format_exc())
            return HttpResponse(json.dumps({"error": u"load failed"}))
        return HttpResponse("ok")
    return HttpResponse("only post allowed")


@csrf_exempt
def download_addressbook(request):
    def _get_phonecall_rawdata(user_id):
        phonecall_rawdata = data_query.phonecall_rawdata.copy()
        phonecall_rawdata["user_id"] = int(user_id)
        call_records_json = data_query.get_phonecall_rawdata(phonecall_rawdata)
        return call_records_json

    if request.method == 'GET':
        uid = request.GET.get("uid")
        apply_id = request.GET.get("pid", None)
        Log().info("download %s addressbook" % uid)
        user = get_object_or_404(User, id=uid)
        addressbook = []
        records = []
        try:
            apply_object = Apply.objects.get(pk=apply_id) if apply_id else None
            if apply_object:
                if apply_object.status not in ['w', 'i', '0']:
                    addressbook_objects = []
                    callrecord_objects = []
                    table = mongo_client['snapshot']['basic_apply']
                    if apply_id:
                        snapshot_data = table.find_one({"apply_info.id": apply_object.id})
                    else:
                        snapshot_data = None
                    if not snapshot_data:
                        addressbook = AddressBook.objects.filter(owner=user)
                        records = CallRecord.objects.filter(owner=user)
                    else:
                        if 'addressbook' in snapshot_data:
                            Log().info('snap_addressbook: %s' % str(snapshot_data['addressbook']))
                            for data in snapshot_data['addressbook']:
                                data.pop('owner')
                                addressbook_objects.append(AddressBook(owner=apply_object.create_by, **data))
                            addressbook = addressbook_objects
                        if 'callrecord' in snapshot_data:
                            Log().info('snap_callrecord: %s' % str(snapshot_data['callrecord']))
                            for data in snapshot_data['callrecord']:
                                data.pop('owner')
                                callrecord_objects.append(CallRecord(owner=apply_object.create_by, **data))
                            records = callrecord_objects
            else:
                addressbook = AddressBook.objects.filter(owner=user)
                records = CallRecord.objects.filter(owner=user)
            w = Workbook()
            ws = w.add_sheet(unicode('手机通讯录', "utf-8"))
            for i, address in enumerate(addressbook):
                ws.write(i, 0, address.phone_number)
                ws.write(i, 1, address.name)  # unicode(address.name, 'utf-8'))
                ws.write(i, 2, datetime.fromtimestamp(address.create_time).strftime("%y-%m-%d"))

            rs = w.add_sheet(unicode('手机通话记录', "utf-8"))

            for i, record in enumerate(records):
                rs.write(i, 0, record.phone_number)
                rs.write(i, 1, record.name)
                rs.write(i, 2, record.duration)
                rs.write(i, 3, record.call_time)
                rs.write(i, 4, record.get_call_type_display())

            rs = w.add_sheet(unicode('运营商通话详单', "utf-8"))
            try:
                new_data = redis_client.hget("USER_INFO:%s" % uid, "mobile_record")
            except Exception, e:
                Log().error(u"call redis error")
                new_data = False

            if new_data:
                call_records = _get_phonecall_rawdata(uid)

                if not call_records or call_records == u'采集失败':
                    call_records = []
                for i, record in enumerate(call_records):
                    # rs.write(i, 0, record["cell_phone"] if record["cell_phone"] else "")
                    rs.write(i, 0, record["other_cell_phone"] if record["other_cell_phone"] else "")
                    rs.write(i, 1, record["call_place"] if record["call_place"] else "")
                    rs.write(i, 2, record["start_time"] if record["start_time"] else "")
                    rs.write(i, 3, record["use_time"] if record["use_time"] else "")
                    rs.write(i, 4, record["call_type"] if record["call_type"] else "")
                    rs.write(i, 5, record["init_type"] if record["init_type"] else "")
            else:
                latest_call = PhoneCall.objects.filter(owner=user).order_by('-id')[:1]
                if len(latest_call) == 1:
                    latest_version = latest_call[0].version
                    call_records = PhoneCall.objects.filter(owner=user, version=latest_version)
                    for i, record in enumerate(call_records):
                        rs.write(i, 0, record.cell_phone if record.cell_phone else "")
                        rs.write(i, 1, record.other_cell_phone if record.other_cell_phone else "")
                        rs.write(i, 2, record.call_place if record.call_place else "")
                        rs.write(i, 3, record.start_time.strftime("%y-%m-%d %H:%M:%S") if record.start_time else "")
                        rs.write(i, 4, record.use_time if record.use_time else "")
                        rs.write(i, 5, record.call_type if record.call_type else "")
                        rs.write(i, 6, record.init_type if record.init_type else "")
                else:
                    call_records = _get_phonecall_rawdata(uid)
                    new_objects = []
                    if not call_records or call_records == u'采集失败':
                        call_records = []
                    for i, record in enumerate(call_records):
                        new_obj = PhoneCall(owner_id=uid, **record)
                        new_objects.append(new_obj)
                        # rs.write(i, 0, record["cell_phone"] if record["cell_phone"] else "")
                        rs.write(i, 0, record["other_cell_phone"] if record["other_cell_phone"] else "")
                        rs.write(i, 1, record["call_place"] if record["call_place"] else "")
                        rs.write(i, 2, record["start_time"] if record["start_time"] else "")
                        rs.write(i, 3, record["use_time"] if record["use_time"] else "")
                        rs.write(i, 4, record["call_type"] if record["call_type"] else "")
                        rs.write(i, 5, record["init_type"] if record["init_type"] else "")
                    if new_objects:
                        PhoneCall.objects.bulk_create(new_objects)
            w.save('t.xls')
        except Exception, e:
            traceback.print_exc()
            return HttpResponse(json.dumps({"error": u"load failed"}))
        response = StreamingHttpResponse(FileWrapper(open('t.xls'), 8192), content_type='application/vnd.ms-excel')
        response['Content-Length'] = os.path.getsize("t.xls")
        response['Content-Disposition'] = 'attachment; filename=%s.xls' % uid
        return response
    return HttpResponse(json.dumps({"error": "get only"}))


def write_xls(body, headers=None, sheet_name=None, workbook=None):
    """将数据写入 xls
    """

    max_len = 60000
    workbook = workbook or xlwt.Workbook()
    sheet_name = sheet_name or 'Sheet1'

    ws = workbook.add_sheet(sheet_name)
    for _cn, _h in enumerate(headers):
        ws.write(0, _cn, _h)

    recursive_deep = len(body) / (max_len * 1.0)
    # ln: line number, ld: line data
    # cn: column number
    for _ln, _ld in enumerate(body[:max_len]):
        _ln += 1
        for _cn, _value in enumerate(_ld):
            ws.write(_ln, _cn, _value)

    # for i in range(1, recursive_deep):
    if recursive_deep > 1:
        start = max_len
        write_xls(body[start:], headers, '%s_%s' % (sheet_name, 1), workbook)

    return workbook


def _get_apply_list(request):
    try:
        stime = get_today()
        etime = get_tomorrow()
        timerange = request.GET.get("time")
        if timerange == "today":
            stime = get_today()
            etime = get_tomorrow()
        elif timerange == "twodays":
            stime = get_yestoday()
            etime = get_tomorrow()
        elif timerange == "yestoday":
            stime = get_yestoday()
            etime = get_today()
        elif timerange == "toweek":
            stime = get_first_day_of_week()
            etime = get_tomorrow()
        elif timerange == "tomonth":
            stime = get_first_day_of_month()
            etime = get_tomorrow()
        else:
            stime = request.GET.get("stime")
            etime = request.GET.get("etime")

        time_filter = request.GET.get("time_filter")
        query_time = None
        if time_filter == "review":
            query_time = Q(finish_time__lt=etime, finish_time__gt=stime)
        else:
            query_time = Q(create_at__lt=etime, create_at__gt=stime)

        query_status = None
        status = request.GET.get("status")
        if status == "waiting":
            query_status = Q(status='0') | Q(status='i')
        elif status == "passed":
            query_status = Q(status='y')
        elif status == "rejected":
            query_status = Q(status='n')
        elif status == "auto_rejected":
            query_status = Q(status='b')
        elif status == "back":
            query_status = Q(status='r')
        else:
            query_status = Q()

        review_type = request.GET.get("type")
        query_type = Q(type__lte='9', type__gte='0')
        if review_type == 'basic':
            query_type = Q(type='0')
        elif review_type == 'promotion':
            query_type = Q(type__lte='8', type__gte='1')
        elif review_type == 'second':
            query_type = Q(type='s')
        elif review_type == 'loan':
            query_type = Q(type='0') | Q(type='s')
        elif review_type == 'all':
            query_type = Q(type__lte='9', type__gte='0') | Q(type='s')

        apply_list = Apply.objects.filter(query_time & query_status & query_type)
        return (apply_list, stime, etime)
    except Exception, e:
        traceback.print_exc()
        return ([], "", "")


# 审批绩效考核表(每次审批一条记录)
def download_review_table_1(request):
    """审批绩效考核表(每次审批一条记录)
    """
    if request.method == 'GET':
        apply_list, stime, etime = _get_apply_list(request)
        try:
            # apply_list = Apply.objects.filter()[:300]
            # 写标题
            headers = [u'订单编号', u'客户类型', u'申请日期', u'处理人姓名', u'开始时间', u'结束时间', u'处理时长', u'审批结果', u'审批备注']
            # for _cn, _h in zip(range(len(headers)), headers):
            # ws.write(0, _cn, _h)

            # 单条 sql 效率更高(之前是 loop). 数据集, 不是queryset 效率更高, 字段的可读化(profile_job)手动处理
            apply_datas = apply_list.values('id', 'create_at', 'status', 'review__reviewer__username',
                                            'create_by__profile__job', 'review__create_at', 'review__finish_time',
                                            'review__review_res')
            # 列字段
            header_keys = ['id', 'create_by__profile__job', 'create_at', 'review__reviewer__username',
                           'review__create_at', 'review__finish_time', 'cost_time', 'status']
            header_range = range(len(header_keys))
            # 可读化字典, {"1": "学生"}
            job_type_dic = dict(Profile.job_type_t)
            review_status_dic = dict(review_status_t)
            apply_status_dic = dict(Apply.apply_status_t)
            # 字段转化, 如 时间可读化, 字段可读化
            values_dic = dict(
                create_by__profile__job=lambda k: job_type_dic.get(k, ''),
                create_at=lambda v: v.strftime("%Y-%m-%d %H:%M:%S"),
                review__create_at=lambda v: v.strftime("%Y-%m-%d %H:%M:%S"),
                review__finish_time=lambda v: v.strftime("%Y-%m-%d %H:%M:%S"),
            )
            # 写数据
            # _ln: line number, _cn: column number
            body_datas = []
            for _ln, _ad in enumerate(apply_datas):
                line_datas = []
                for _cn, _hk in zip(header_range, header_keys):
                    value = _ad.get(_hk) or ''

                    if value and _hk in values_dic:
                        value = values_dic[_hk](value)
                    elif _hk == 'status':
                        # status: 先取 review_res, 如果没有从 status 取.
                        value = _ad.get('review__review_res')
                        value = review_status_dic.get(value, '') if value else apply_status_dic.get(_ad.get(_hk), '')
                    elif _hk == 'cost_time' and _ad.get('review__finish_time'):
                        cost_time = _ad['review__finish_time'] - _ad['review__create_at']
                        value = "%s:%s:%s" % (cost_time.days, cost_time.seconds / 60, cost_time.seconds % 60)
                    line_datas.append(value)

                body_datas.append(line_datas)

            xls = write_xls(body_datas, headers, 'review')
            xls.save('t.xls')

            response = StreamingHttpResponse(FileWrapper(open('t.xls'), 8192), content_type='application/vnd.ms-excel')
            response['Content-Length'] = os.path.getsize("t.xls")
            response['Content-Disposition'] = 'attachment; filename=table1%s-%s.xls' % (stime, etime)

            return response

        except Exception, e:
            traceback.print_exc()

            return HttpResponse(json.dumps({"error": u"load failed"}))

    return HttpResponse(json.dumps({"error": "get only"}))


# 审批绩效考核表(按照订单提交时间 暂时废弃)
def download_review_table_2(request):
    if request.method == 'GET':
        apply_list, stime, etime = _get_apply_list(request)
        try:
            w = Workbook()
            ws = w.add_sheet('review')
            ws.write(0, 0, unicode("贷款编号", 'utf-8'))
            ws.write(0, 1, unicode("客户类型", 'utf-8'))
            ws.write(0, 2, unicode("申请日期", 'utf-8'))
            ws.write(0, 3, unicode("客户姓名", 'utf-8'))
            ws.write(0, 4, unicode("渠道来源", 'utf-8'))
            ws.write(0, 5, unicode("审批结果", 'utf-8'))
            ws.write(0, 6, unicode("拒绝原因", 'utf-8'))
            i = 1
            for apply in apply_list:
                profiles = Profile.objects.filter(owner=apply.create_by)
                ws.write(i, 0, apply.id)
                ws.write(i, 1, profiles[0].get_job_display() if len(profiles) == 1 else "")
                ws.write(i, 2, apply.create_at.strftime("%Y-%m-%d %H:%M:%S"))
                ws.write(i, 3, apply.create_by.name)
                ws.write(i, 4, apply.create_by.channel)
                ws.write(i, 5, apply.get_status_display())
                if apply.status == "b":  # 机器拒绝 输出机器拒绝的原因
                    check_status = CheckStatus.objects.filter(owner=apply.create_by)
                    ws.write(i, 6, check_status[0].get_auto_check_status_display() if len(check_status) == 1 else "")
                else:  # 人工拒绝打出人工拒绝的标签
                    ws.write(i, 6, "")
                    # reviews =
                i += 1
            w.save('t.xls')
            response = StreamingHttpResponse(FileWrapper(open('t.xls'), 8192), content_type='application/vnd.ms-excel')
            response['Content-Length'] = os.path.getsize("t.xls")
            response['Content-Disposition'] = 'attachment; filename=%s-%s.xls' % (stime, etime)
            return response
        except Exception, e:
            traceback.print_exc()
            return HttpResponse(json.dumps({"error": str(e)}))
    return HttpResponse(json.dumps({"error": "get only"}))


# BI报表(每个申请一条记录)
def download_review_table_3(request):
    """BI报表(每个申请一条记录)
    """
    if request.method == 'GET':
        apply_list, stime, etime = _get_apply_list(request)
        try:

            # apply_list = Apply.objects.filter(id__lte=12639, id__gte=11639)
            headers = [u'订单编号', u'订单类型', u'客户类型', u'申请日期', u'客户姓名', u'渠道来源', u'审批结果', u'拒绝原因']

            # 单条 sql 效率更高(之前是 loop). 数据集, 不是queryset 效率更高, 字段的可读化(profile_job)手动处理
            apply_datas = apply_list.values('id', 'type', 'create_by__profile__job', 'create_at', 'create_by__name',
                                            'create_by__channel', 'status', 'create_by__checkstatus__auto_check_status')

            # 列字段
            header_keys = ['id', 'type', 'create_by__profile__job', 'create_at', 'create_by__name',
                           'create_by__channel', 'status', 'create_by__checkstatus__auto_check_status']
            header_range = range(len(header_keys))
            # 可读化字典, {"1": "学生"}
            job_type_dic = dict(Profile.job_type_t)
            # review_status_dic = dict(review_status_t)
            apply_type_dic = dict(Apply.apply_type_t)
            apply_status_dic = dict(Apply.apply_status_t)
            check_apply_status_dic = dict(CheckStatus.auto_check_status_t)
            # 字段转化, 如 时间可读化, 字段可读化
            values_dic = dict(
                type=lambda k: apply_type_dic.get(k, ''),
                create_by__profile__job=lambda k: job_type_dic.get(k, ''),
                create_at=lambda v: v.strftime("%Y-%m-%d %H:%M:%S"),
                review__create_at=lambda v: v.strftime("%Y-%m-%d %H:%M:%S"),
                status=lambda k: apply_status_dic.get(k, ''),
            )

            # 用 raw sql 也很麻烦, 所以就使用原来的算法
            account = {u'总计': {'label': {}}}
            # 写数据
            # _ln: line number, _cn: column number
            body_datas = []
            for _ln, _ad in enumerate(apply_datas):
                line_datas = []
                for _cn, _hk in zip(header_range, header_keys):
                    value = _ad.get(_hk) or ''

                    if value and _hk in values_dic:
                        value = values_dic[_hk](value)
                    elif _hk == 'create_by__checkstatus__auto_check_status':
                        _channel_key = _ad.get('create_by__channel')
                        account.setdefault(_channel_key, {'label': {}})
                        if _ad.get('status') == 'b':
                            # status: 先取 review_res, 如果没有从 status 取.
                            value = _ad.get('create_by__checkstatus__auto_check_status', '')
                            value = check_apply_status_dic.get(value, '').decode('utf8')
                        else:
                            review = Review.objects.filter(order=_ad.get('id')).order_by("-id").first()
                            if review:
                                review_labels = [l for l in review.get_label_list().all() if l.is_reject()]
                                value = ",".join(rl.display() for rl in review_labels)

                                for l in review_labels:
                                    dict_addcount(account[_channel_key]["label"], l.name)
                                    dict_addcount(account[u'总计']["label"], l.name)

                    line_datas.append(value)
                body_datas.append(line_datas)

            xls = write_xls(body_datas, headers, 'review')

            sheet_1_headers = u'渠道,总单量,机器拒绝量,人工审批单量,通过量,拒绝量,通过率,拒绝原因'.split(',')

            group_by_field = 'create_by__channel'
            apply_count_list = apply_list.values(group_by_field)

            count_dic = dict(
                counts=apply_count_list.annotate(count=Count(group_by_field)),
                mechine_reject_counts=apply_count_list.filter(status='b').annotate(count=Count(group_by_field)),
                manual_counts={},
                pass_counts=apply_count_list.filter(status='y').annotate(count=Count(group_by_field)),
                reject_counts=apply_count_list.filter(status='n').annotate(count=Count(group_by_field)),
                pass_rate={},
                # label_counts=apply_count_list.exclude(status='b').annotate(count=Count(group_by_field)),
            )
            count_dic = {_k: {_v['create_by__channel']: _v['count'] for _v in _lv} for _k, _lv in count_dic.items()}
            channel_keys = count_dic['counts'].keys()
            for _k, _v in count_dic.items():
                _v[u'总计'] = sum(_v.values())
            channel_keys.append(u'总计')

            count_keys = 'counts, mechine_reject_counts, manual_counts, pass_counts, reject_counts, pass_rate, reject_reason'.split(
                ', ')
            # ck: column key
            sheet_1_body_datas = []
            for _ln, _channel_key in enumerate(channel_keys):
                _ln *= 2
                sheet_1_line_datas = []
                sheet_1_line_2_datas = ['' for _i in range(count_keys.index('reject_reason') + 1)]
                sheet_1_line_datas.append(_channel_key)
                for _cn, _ck in enumerate(count_keys):
                    value = count_dic.get(_ck)
                    value = value.get(_channel_key, 0) if value else 0
                    if _ck == 'manual_counts':
                        value = count_dic['counts'][_channel_key] - count_dic['mechine_reject_counts'].get(_channel_key,
                                                                                                           0)
                        count_dic['manual_counts'][_channel_key] = value
                    elif _ck == 'pass_rate':
                        pass_count = count_dic['pass_counts'].get(_channel_key, 0)
                        apply_count = count_dic['counts'].get(_channel_key, 0)
                        value = "%.2f%%" % (round(float(pass_count) / apply_count, 4) * 100 if apply_count != 0 else 0)
                    elif _ck == 'reject_reason':
                        reject_count = count_dic['reject_counts'].get(_channel_key, 0)
                        for (label, count) in sorted(account[_channel_key]["label"].items(), key=lambda d: -d[1]):
                            _cn += 1
                            sheet_1_line_datas.append(label)
                            line_2_value = "%.2f%%" % (
                            round(float(count) / reject_count, 4) * 100 if reject_count != 0 else 0)
                            sheet_1_line_2_datas.append(line_2_value)
                        continue

                    sheet_1_line_datas.append(value)

                sheet_1_body_datas.append(sheet_1_line_datas)
                sheet_1_body_datas.append(sheet_1_line_2_datas)

            xls = write_xls(sheet_1_body_datas, sheet_1_headers, u'统计报表1', xls)

            # 只统计审批报表需要的三大原因
            reasons = (u"与多家贷款公司联系异常", u"催收通话记录"), (u"父母是否虚假",), (u"不符合进件政策", u"三方负面信息", u"与父母无联系")

            sheet_2_headers = u'渠道,总单量,机器拒绝量,人工审批单量,通过量,拒绝量,通过率,详单异常,联系人虚假,其他'.split(',')

            sheet_2_body_datas = []
            for _ln, _channel_key in enumerate(channel_keys):
                sheet_2_line_datas = []
                sheet_2_line_datas.append(_channel_key)
                for _cn, _ck in enumerate(count_keys[:-1]):
                    value = count_dic.get(_ck)
                    value = value.get(_channel_key, 0) if value else 0
                    if _ck == 'manual_counts':
                        value = count_dic['counts'][_channel_key] - count_dic['mechine_reject_counts'].get(_channel_key,
                                                                                                           0)
                        count_dic['manual_counts'][_channel_key] = value
                    elif _ck == 'pass_rate':
                        pass_count = count_dic['pass_counts'].get(_channel_key, 0)
                        apply_count = count_dic['counts'].get(_channel_key, 0)
                        value = "%.2f%%" % (round(float(pass_count) / apply_count, 4) * 100 if apply_count != 0 else 0)

                    sheet_2_line_datas.append(value)

                reject_count = count_dic['reject_counts'].get(_channel_key, 0)

                for lables in (reasons):
                    count = 0
                    _cn += 1
                    # if _channel_key == u'总计' or reject_count <= 0:
                    if reject_count <= 0:
                        sheet_2_line_datas.append('0.00%')
                        continue

                    for label in lables:
                        count += account[_channel_key]["label"][label] if label in account[_channel_key]["label"] else 0
                    sheet_2_line_datas.append(
                        "%.2f%%" % (round(float(count) / reject_count, 4) * 100 if reject_count != 0 else 0))

                sheet_2_body_datas.append(sheet_2_line_datas)

            xls = write_xls(sheet_2_body_datas, sheet_2_headers, u'统计报表2', xls)
            xls.save('t.xls')
            response = StreamingHttpResponse(FileWrapper(open('t.xls'), 8192), content_type='application/vnd.ms-excel')
            response['Content-Length'] = os.path.getsize("t.xls")
            response['Content-Disposition'] = 'attachment; filename=table1%s-%s.xls' % (stime, etime)

            return response
        except Exception, e:
            traceback.print_exc()
            return HttpResponse(json.dumps({"error": str(e)}))

    return HttpResponse(json.dumps({"error": "get only"}))


def _download_review_table_3(request):
    """BI报表(每个申请一条记录)
    """
    if request.method == 'GET':
        apply_list, stime, etime = _get_apply_list(request)
        try:

            # apply_list = Apply.objects.filter(id__lte=12639, id__gte=11639)
            w = Workbook()
            ws = w.add_sheet('review')

            headers = [u'贷款编号', u'订单类型', u'客户类型', u'申请日期', u'客户姓名', u'渠道来源', u'审批结果', u'拒绝原因']
            for _cn, _h in zip(range(len(headers)), headers):
                # BI报表(每个申请一条记录)
                ws.write(0, _cn, _h)

            # 单条 sql 效率更高(之前是 loop). 数据集, 不是queryset 效率更高, 字段的可读化(profile_job)手动处理
            # apply_datas = apply_list.values('id', 'type', 'create_by__profile__job', 'create_at', 'create_by__name', 'create_by__channel', 'status', 'create_by__check_status__auto_check_status')

            i = 1
            all_dict = {"label": {}}
            account = {}
            reject_count = {"all": 0}
            for apply in apply_list:
                profiles = Profile.objects.filter(owner=apply.create_by)
                ws.write(i, 0, apply.id)
                ws.write(i, 1, apply.get_type_display())
                ws.write(i, 2, profiles[0].get_job_display() if len(profiles) == 1 else "")
                ws.write(i, 3, apply.create_at.strftime("%Y-%m-%d %H:%M:%S"))
                ws.write(i, 4, apply.create_by.name)
                channel = apply.create_by.channel
                ws.write(i, 5, channel)
                ws.write(i, 6, apply.get_status_display())
                dict_addmap(account, channel)
                dict_addmap(account[channel], "label")
                dict_addcount(account[channel], "count")
                dict_addcount(all_dict, "count")
                if apply.status == "y":
                    dict_addcount(account[channel], "pass_count")
                    dict_addcount(all_dict, "pass_count")
                elif apply.status == "n":
                    dict_addcount(account[channel], "reject_count")
                    dict_addcount(all_dict, "reject_count")

                if apply.status == "b":  # 机器拒绝 输出机器拒绝的原因
                    dict_addcount(account[channel], "mechine_reject_count")
                    dict_addcount(all_dict, "mechine_reject_count")
                    check_status = CheckStatus.objects.filter(owner=apply.create_by)
                    ws.write(i, 7, check_status[0].get_auto_check_status_display() if len(check_status) == 1 else "")
                else:  # 人工拒绝打出人工拒绝的标签
                    review = _get_last_review(apply)
                    label = ""
                    if review:
                        label = ",".join(l.display() for l in review.get_label_list().all() if l.is_reject())
                        for l in review.get_label_list().all():
                            if l.is_reject():
                                dict_addcount(account[channel]["label"], l.name)
                                dict_addcount(all_dict["label"], l.name)
                    ws.write(i, 7, label)
                i += 1

            ws = w.add_sheet(unicode('统计报表1', "utf-8"))

            sheet_1_headers = u'渠道,总单量,机器拒绝量,人工审批单量,通过量,拒绝量,通过率,拒绝原因'.split(',')
            for _cn, _h in zip(range(len(sheet_1_headers)), sheet_1_headers):
                ws.write(0, _cn, _h)

            i = 0
            i += 1
            for (channel, channel_count) in account.items():
                ws.write(i + 1, 1, channel)
                all_apply_count = channel_count["count"] if "count" in channel_count else 0
                mechine_reject_count = channel_count[
                    "mechine_reject_count"] if "mechine_reject_count" in channel_count else 0
                apply_count = all_apply_count - mechine_reject_count
                pass_count = channel_count["pass_count"] if "pass_count" in channel_count else 0
                reject_count = channel_count["reject_count"] if "reject_count" in channel_count else 0
                ws.write(i + 1, 2, all_apply_count)
                ws.write(i + 1, 3, mechine_reject_count)
                ws.write(i + 1, 4, apply_count)
                ws.write(i + 1, 5, pass_count)
                ws.write(i + 1, 6, reject_count)
                ws.write(i + 1, 7,
                         "%.2f%%" % (round(float(pass_count) / apply_count, 4) * 100) if apply_count != 0 else 0)
                j = 7
                for (label, count) in sorted(account[channel]["label"].items(), key=lambda d: -d[1]):
                    j += 1
                    ws.write(i, j, "%s" % label)
                    ws.write(i + 1, j,
                             "%.2f%%" % (round(float(count) / reject_count, 4) * 100 if reject_count != 0 else 0))
                i += 2

            ws.write(i + 1, 1, unicode("总计", "utf-8"))
            all_apply_count = all_dict["count"] if "count" in all_dict else 0
            mechine_reject_count = all_dict["mechine_reject_count"] if "mechine_reject_count" in all_dict else 0
            apply_count = all_apply_count - mechine_reject_count
            pass_count = all_dict["pass_count"] if "pass_count" in all_dict else 0
            reject_count = all_dict["reject_count"] if "reject_count" in all_dict else 0
            ws.write(i + 1, 2, all_apply_count)
            ws.write(i + 1, 3, mechine_reject_count)
            ws.write(i + 1, 4, apply_count)
            ws.write(i + 1, 5, pass_count)
            ws.write(i + 1, 6, reject_count)
            ws.write(i + 1, 7, "%.2f%%" % (round(float(pass_count) / apply_count, 4) * 100) if apply_count != 0 else 0)
            j = 7
            for (label, count) in sorted(all_dict["label"].items(), key=lambda d: -d[1]):
                j += 1
                ws.write(i, j, "%s" % label)
                ws.write(i + 1, j, "%.2f%%" % (round(float(count) / reject_count, 4) * 100 if reject_count != 0 else 0))

            # 只统计审批报表需要的三大原因
            reasons = (u"与多家贷款公司联系异常", u"催收通话记录"), (u"父母是否虚假",), (u"不符合进件政策", u"三方负面信息", u"与父母无联系")
            ws = w.add_sheet(unicode('统计报表2', "utf-8"))

            sheet_2_headers = u'渠道,总单量,机器拒绝量,人工审批单量,通过量,拒绝量,通过率,详单异常,联系人虚假,其他'.split(',')
            for _cn, _h in zip(range(len(sheet_2_headers)), sheet_2_headers):
                ws.write(0, _cn, _h)

            i = 0
            i += 1

            for (channel, channel_count) in account.items():
                ws.write(i + 1, 1, channel)
                all_apply_count = channel_count["count"] if "count" in channel_count else 0
                mechine_reject_count = channel_count[
                    "mechine_reject_count"] if "mechine_reject_count" in channel_count else 0
                apply_count = all_apply_count - mechine_reject_count
                pass_count = channel_count["pass_count"] if "pass_count" in channel_count else 0
                reject_count = channel_count["reject_count"] if "reject_count" in channel_count else 0
                ws.write(i + 1, 2, all_apply_count)
                ws.write(i + 1, 3, mechine_reject_count)
                ws.write(i + 1, 4, apply_count)
                ws.write(i + 1, 5, pass_count)
                ws.write(i + 1, 6, reject_count)
                ws.write(i + 1, 7,
                         "%.2f%%" % (round(float(pass_count) / apply_count, 4) * 100) if apply_count != 0 else 0)
                j = 7
                for lables in (reasons):
                    count = 0
                    for label in lables:
                        count += account[channel]["label"][label] if label in account[channel]["label"] else 0
                    j += 1
                    ws.write(i + 1, j,
                             "%.2f%%" % (round(float(count) / reject_count, 4) * 100 if reject_count != 0 else 0))
                i += 2

            ws.write(i + 1, 1, unicode("总计", "utf-8"))
            all_apply_count = all_dict["count"] if "count" in all_dict else 0
            mechine_reject_count = all_dict["mechine_reject_count"] if "mechine_reject_count" in all_dict else 0
            apply_count = all_apply_count - mechine_reject_count
            pass_count = all_dict["pass_count"] if "pass_count" in all_dict else 0
            reject_count = all_dict["reject_count"] if "reject_count" in all_dict else 0
            ws.write(i + 1, 2, all_apply_count)
            ws.write(i + 1, 3, mechine_reject_count)
            ws.write(i + 1, 4, apply_count)
            ws.write(i + 1, 5, pass_count)
            ws.write(i + 1, 6, reject_count)
            ws.write(i + 1, 7, "%.2f%%" % (round(float(pass_count) / apply_count, 4) * 100) if apply_count != 0 else 0)
            j = 7
            for lables in (reasons):
                count = 0
                for label in lables:
                    count += all_dict["label"][label] if label in all_dict["label"] else 0
                j += 1
                ws.write(i + 1, j, "%.2f%%" % (round(float(count) / reject_count, 4) * 100 if reject_count != 0 else 0))

            w.save('t.xls')
            response = StreamingHttpResponse(FileWrapper(open('t.xls'), 8192), content_type='application/vnd.ms-excel')
            response['Content-Length'] = os.path.getsize("t.xls")
            response['Content-Disposition'] = 'attachment; filename=table2%s-%s.xls' % (stime, etime)
            return response
        except Exception, e:
            traceback.print_exc()
            return HttpResponse(json.dumps({"error": str(e)}))
    return HttpResponse(json.dumps({"error": "get only"}))


def strbin(s):
    return ''.join(format(ord(i), '0>8b') for i in s)


def get_call(request):
    if request.method == 'GET':
        uid = request.GET.get("uid")
        try:
            params = '{"uid":%s}' % uid
            # bin_params = bitarray.bitarray()
            # bin_params = strbin(params)
            call_command('gearman_submit_job', 'get_call', params.encode("utf-8"))
            # result = gearman_client.submit_job("get_call", params, background=True)
        except Exception, e:
            traceback.print_exc()
            return HttpResponse(json.dumps({"error": u"load failed"}))
        return HttpResponse(json.dumps({"error": "ok"}))
    return HttpResponse(json.dumps({"error": "get only"}))


def get_client(request, client_type):
    """ 还款良好客户, 逾期客户"""
    months_no = -3
    staff = Employee.objects.get(user=request.user)
    if request.method == 'GET':
        # data = get_my_review_relative_info(request.user.id, False)
        if client_type == "good":
            data = get_apply_from_install([staff.user.id], months_no, False)
        elif client_type == "overdue":
            data = get_apply_from_install([staff.user.id], months_no, True)
        is_overdue = (client_type == "overdue")
        client_data = data.get(int(request.user.id), [])
        html = render_to_response(
            'review/client_list.html',
            dict(clients=client_data, is_overdue=is_overdue), context_instance=RequestContext(request))

        return html

if __name__ == '__main__':
    review = Review.objects.filter(order_id=11).order_by('-create_at').first()
    review.finish_time = datetime.now()
    review.review_res = 's1'
    print review
    # review.save()
