# -*- coding:utf-8 -*-
from business_manager.review.models import Review
from business_manager.review import mongo_client, redis_client
from business_manager.collection.models import InstallmentDetailInfo
from business_manager.order.apply_models import Apply
from django.db.models import Q
from dateutil.relativedelta import relativedelta
from datetime import date
import time
import hashlib
import datetime


def get_apply_from_install(reviewer_lists, months_no, is_overdue):
    today = date.today()
    before = date.today() + relativedelta(months=months_no)
    pos_a = time.time()
    if is_overdue:
        installs = InstallmentDetailInfo.objects.filter(Q(should_repay_time__gt = before) & Q(should_repay_time__lt = today) & Q(repay_status__in = [2,8])).values("id", "repayment")
    else:
        installs = InstallmentDetailInfo.objects.filter(Q(should_repay_time__gt = before) & Q(should_repay_time__lt = today) & ~Q(repay_status__in = [2,8])).values("id", "repayment")
    res = {d["repayment"]: d for d in installs}
    pos_b = time.time()
    print pos_b - pos_a
    repayment_list = [i['repayment'] for i in installs]
    apply_query = Apply.objects.filter(repayment__in=repayment_list)
    apply_lists = apply_query.values('repayment', 'id')
    order_ids = [a['id'] for a in apply_lists]
    pos_c = time.time()

    print 'apply times:', pos_c - pos_b
    # results = {a.repayment: a.id for a in apply_lists}
    # {apply:install}
    new_dict = {a['id']: res[a['repayment']]['repayment']for a in apply_lists}
    review_list = Review.objects.filter(order__id__in=order_ids, order__type__in=['p', 'a', 'b', 'c', 'd', 'e', 's'], review_res='y').values('reviewer_done', 'order')
    print review_list
    pos_d = time.time()
    print pos_d - pos_c
    review_dict = {r['order']: r['reviewer_done'] for r in review_list}
    # {install:reviewer}
    last_data = {new_dict[k]: v for k, v in review_dict.items()}

    ret_list = {}
    for k, v in last_data.items():
        temp_data = {}
        # print 'keys:', k
        install_obj = InstallmentDetailInfo.objects.filter(pk=k)
        if install_obj:
            temp_data['name'] = install_obj[0].repayment.user.name
            temp_data['install_id'] = install_obj[0].id
            temp_data['should_repay_time'] = str(install_obj[0].should_repay_time)
            temp_data['overdue_days'] = install_obj[0].overdue_days
            if v in ret_list:
                ret_list[v] += [temp_data]
            else:
                ret_list[v] = [temp_data]

    return ret_list


def init_dayTable():
    """
    初始化审批专员名单到redis和mongo
    :return:
    """
    wait_dispatch_table = mongo_client['dispatch']['wait_dispatch']
    wait_dispatch_list = wait_dispatch_table.find_one({})
    if not wait_dispatch_list:
        wait_dispatch_table.insert({"apply_ids": []})
    all_reviewer = Employee.objects.filter(post__in=['rm', 'rs', 'r2', 'ad']).values('user')

    all_reviewer_list = sorted([int(ids['user']) for ids in all_reviewer])
    list_hash = hashlib.md5(','.join([str(i) for i in all_reviewer_list])).hexdigest()
    init_reviewer_status = dict(zip(all_reviewer_list, ['offline']*len(all_reviewer_list)))
    all_reviewer_list = list(set(all_reviewer_list))
    reviewer_status = redis_client.hgetall('reviewer_status')
    if reviewer_status:
        reviewer_ids = sorted([int(k) for k, v in reviewer_status.items()])
        ids_hash = hashlib.md5(','.join([str(i) for i in reviewer_ids])).hexdigest()
        if ids_hash != list_hash:
            redis_client.delete('reviewer_status')
            redis_client.hmset('reviewer_status', init_reviewer_status)
    else:
        print init_reviewer_status
        redis_client.hmset('reviewer_status', init_reviewer_status)
    tasks_table = mongo_client['dispatch']['tasks']
    mongo_ids = [i['reviewer_id'] for i in tasks_table.find({}, {'reviewer_id': 1, '_id': 0}).sort('reviewer_id')]
    add_list = set()
    for add_id in all_reviewer_list:
        if add_id not in mongo_ids:
            add_list.add(add_id)
    del_list = set()
    for del_id in mongo_ids:
        if del_id not in all_reviewer_list:
            del_list.add(del_id)
    add_list = list(add_list)
    del_list = list(del_list)
    print add_list, del_list
    task_reviewer = tasks_table.find_one()
    if task_reviewer:
        if add_list:
            tasks_table.insert([{'reviewer_id': i, 'task_list': []} for i in add_list])
        tasks_table.remove({'reviewer_id': {"$in": del_list}})
    else:
        tasks_table.insert([{'reviewer_id': i, 'task_list': []} for i in add_list])
    record_table = mongo_client['dispatch']['daily_records']
    day = datetime.datetime.now().date().strftime('%Y%m%d')
    data = record_table.find_one({'day': day}, {'data': 1, '_id': 0})
    print data
    months_no = -3
    datas = get_apply_from_install(all_reviewer_list, months_no,  True)
    # print 'overdue:', datas
    overdue_dict = {int(k): len(v) for k, v in datas.items() if int(k) in all_reviewer_list}
    print overdue_dict
    total_overdue_num = sum(overdue_dict.values())
    init_data = [{'reviewer_id': str(i), 'apply_list': [], 'total_time': 0,
                  'average_time': 0, 'pass_average_time': 0, 'reject_average_time': 0,
                  "reject_total_time": 0, "pass_total_time": 0, "pass_mount": 0, "reject_mount":0, "back_mount": 0,
                  "first_pass_mount":0, "first_reject_mount":0, "first_back_mount":0,
                  "second_pass_mount":0, "second_reject_mount":0, "second_back_mount":0,
                  "today_total_tasks": 0, "overdue_apply_num": overdue_dict.get(i, 0)}
                 for i in all_reviewer_list]
    if not data:
        record_table.insert({'day': day, 'data': init_data, "today_total_tasks": 0, "today_expect_tasks": 10000,
                             "total_overdue_num": total_overdue_num})
    else:
        print 'has data already at', day
        pass
    return all_reviewer_list
