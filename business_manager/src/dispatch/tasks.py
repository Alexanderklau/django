# -*- coding: utf-8 -*-
#!/usr/bin/python

import datetime
import time
import signal
from celery.utils.log import get_task_logger
from celery import Task
import celery
from worker import app
import pymongo
import redis
# from pony.orm import select, db_session, desc, commit
import business_manager.settings as settings
from celery.result import AsyncResult
import traceback
import json

logger = get_task_logger('risk_task')


def create_redis_connection():
    # r = redis.StrictRedis(host=conf.get('redis', 'host'), port=conf.getint('redis', 'port'),
    #                       password=conf.get('redis', 'password'), db=1)
    r = redis.StrictRedis(host=settings.REDIS['HOST'], port=settings.REDIS['PORT'],
                          password=settings.REDIS['AUTH'], db=0)
    return r
redis_connection = create_redis_connection()
if settings.MONGO["USER"]:
    mongo_uri = 'mongodb://%s:%s@%s:%d/%s' % (settings.MONGO["USER"], settings.MONGO["AUTH"],
                                              settings.MONGO["HOST"], settings.MONGO["PORT"],
                                              settings.MONGO["DB"])
else:
    mongo_uri = 'mongodb://%s:%d/%s' % (settings.MONGO["HOST"], settings.MONGO["PORT"],
                                        settings.MONGO["DB"])

mongo_connection = pymongo.MongoClient(mongo_uri, serverSelectionTimeoutMS=30000)
mongo_collection = mongo_connection['dispatch']


class InterruptException(Exception):
    pass


def signal_handler(*args):
    raise InterruptException


def div_list(ls,n):
    if not isinstance(ls,list) or not isinstance(n,int):
        return []
    ls_len = len(ls)
    if n<=0 or 0==ls_len:
        return []
    if n > ls_len:
        return []
    elif n == ls_len:
        return [[i] for i in ls]
    else:
        j = ls_len/n
        k = ls_len%n
        ### j,j,j,...(前面有n-1个j),j+k
        #步长j,次数n-1
        ls_return = []
        for i in xrange(0,(n-1)*j,j):
            ls_return.append(ls[i:i+j])
        #算上末尾的j+k
        ls_return.append(ls[(n-1)*j:])
        return ls_return[::-1]


class ExecutionError(Exception):
    pass


@app.task(bind=True, base=Task, track_started=True, throws=(ExecutionError,))
def execute_dispatch(self, apply_list=None, task_type='new_apply', metadata={}):
    try:
        signal.signal(signal.SIGINT, signal_handler)
        max_idle_time = settings.MAX_IDLE_TIME
        start_time = datetime.datetime.now()
        self.update_state(state='STARTED', meta={'start_time': start_time.strftime('%Y-%m-%d %H:%M:%S'), 'custom_message': 'start dispatch for %s' % apply_list})
        logger.debug("Executing dispatch:%s", apply_list)
        logger.info("task=execute_dispatch state=load_ds ds_id=%s", apply_list)
        reviewer_status = redis_connection.hgetall('reviewer_status')
        all_reviewers = [int(k) for k, v in reviewer_status.items()]
        offline_ids = []
        online_ids = []
        for r in all_reviewers:
            reviewer_key = 'reviewer:%s' % r
            status = redis_connection.get(reviewer_key)
            print reviewer_key, status
            if not status:
                offline_ids.append(r)
            else:
                online_ids.append(r)
        if offline_ids:
            redis_connection.hmset('reviewer_status', dict(zip(offline_ids, ['offline']*len(offline_ids))))
        if online_ids:
            redis_connection.hmset('reviewer_status', dict(zip(online_ids, ['online']*len(online_ids))))
        online_reviewers = online_ids
        offline_reviewers = offline_ids
        # reviewer_applies = redis_connection.hgetall('reviewer_applies')
        tasks_table = mongo_collection['tasks']
        # doing_tasks = tasks_table.find({'reviewer_id': {'$in': online_reviewers}},
        #                                {'_id': 0})
        offline_tasks = list(tasks_table.find({'reviewer_id': {'$in': offline_reviewers}},
                                              {'_id': 0}))
        dispatch_list = []
        reviewer_outtimer = []
        if apply_list:
            dispatch_list += apply_list

        for i in offline_tasks:
            dispatch_list += i['task_list']
            if i['task_list']:
                reviewer_outtimer.append(i['reviewer_id'])
        if task_type == 'change_status':
            doing_tasks = tasks_table.find({'reviewer_id': {'$in': online_reviewers}},
                                           {'_id': 0})
            for t in doing_tasks:
                dispatch_list += t['task_list']

        print 'dispa list:', dispatch_list
        # for k in doing_tasks:
        #     offline_apply_list = [int(j['apply_id']) for j in k['task_list']]
        #     offline_reviewer_tasks = {k['reviewer_id']: offline_apply_list}
        # record_table = mongo_collection['daily_records']
        # data = record_table.find_one({'day': date}, {'data': 1, '_id': 0})
        data = tasks_table.find({})
        wait_dispatch_table = mongo_collection['wait_dispatch']
        outer_tasks = wait_dispatch_table.find_one({})
        outer_tasks_list = []
        if outer_tasks:
            outer_tasks_list = outer_tasks["apply_ids"]
        dispatch_list += outer_tasks_list
        dispatch_list = list(set(dispatch_list))
        if data:
            # reviewer_outtimer = {k: v['apply_list'] for k, v in data.items()
            #                      if k in online_reviewers and v['total_time'] > (start_time+max_idle_time)}
            # outer_ids = reviewer_outtimer.keys()
            # outer_ids = reviewer_outtimer
            # for i in outer_ids:
            #     outer_tasks_list += offline_reviewer_tasks[i]
            # dispatch_list += outer_tasks_list
            print online_ids
            reviewer_result = {d["reviewer_id"]: d['task_list'] for d in data if d['reviewer_id'] in online_ids}
            reviewer_sorted = sorted(reviewer_result.items(), key=lambda d: len(d[1]))
            len_dispatch = len(dispatch_list)
            len_reviewer = len(reviewer_sorted)
            divide = len_reviewer if len_reviewer <= len_dispatch else len_dispatch
            dispatch_result = div_list(dispatch_list, divide) if divide else dispatch_list

            last_dispatch = []
            print 'fidff:', dispatch_result
            order_ids = [i[0] for i in reviewer_sorted]
            print order_ids
            i = 0
            for update_id in order_ids:
                print i, update_id
                tasks_table.update({"reviewer_id": update_id},
                                           {"$set":
                                                {"task_list": dispatch_result[i]
                                                 }
                                            })
                dispatch_result.pop(i)
            print dispatch_result
            last_dispatch += dispatch_result
            if last_dispatch and isinstance(last_dispatch[0], list):
                last_dispatch = reduce(lambda x, y: x+y, last_dispatch)
            print "last_dispatch:", last_dispatch
            wait_dispatch_table.update({}, {"$set": {"apply_ids":  last_dispatch}}, True)
            for clear_id in reviewer_outtimer:
                tasks_table.update({"reviewer_id": clear_id},
                                   {"$set": {"task_list": []}}, upsert=False, multi=True)
            # Delete Job_id
            redis_connection.delete(DispatchTask._job_lock_id(apply_list))

            if dispatch_result:
                wait_dispatch_table.update({}, {"$set": {"apply_ids":  dispatch_result}}, True)
                metadata.update({'start_time': start_time.strftime('%Y-%m-%d %H:%M:%S'), "error":"has not dispatch apply id", 'apply_id': apply_list})
        else:
            # Delete Job_id
            redis_connection.delete(DispatchTask._job_lock_id(apply_list))
            metadata.update({'start_time': start_time.strftime('%Y-%m-%d %H:%M:%S'), "reviewer_id": '', 'apply_id': apply_list, "error": "no daily data"})
            self.update_state(state='SUCCESS', meta=metadata)
            logger.error('no daily data')

    except Exception as error:
        traceback.print_exc()
        self.update_state(state='STARTED', meta={'start_time': start_time.strftime('%Y-%m-%d %H:%M:%S'), 'error': str(error), 'custom_message': 'error dispatch for %s' % apply_list})
        traceback.print_exc()
        logger.debug('retry job:%s', apply_list)
        raise ExecutionError(error)
    return metadata


@app.task(base=Task, track_started=True, throws=(ExecutionError,))
def refresh_tasks():
    reviewer_status = redis_connection.hgetall('reviewer_status')
    all_reviewers = [int(k) for k, v in reviewer_status.items()]
    offline_ids = []
    for r in all_reviewers:
        reviewer_key = 'reviewer:%s' % r
        status = redis_connection.get(reviewer_key)
        print reviewer_key, status
        if not status:
            offline_ids.append(r)
    if offline_ids:
        redis_connection.hmset('reviewer_status', dict(zip(offline_ids, ['offline']*len(offline_ids))))
    offline_reviewers = offline_ids
    tasks_table = mongo_collection['tasks']
    wait_dispatch_table = mongo_collection['wait_dispatch']
    offline_tasks = list(tasks_table.find({'reviewer_id': {'$in': offline_reviewers}},
                                          {'_id': 0}))
    wait_list = []
    reviewer_outtimer = []
    for i in offline_tasks:
        wait_list += i['task_list']
        if i['task_list']:
            reviewer_outtimer.append(i['reviewer_id'])
    print wait_list
    for clear_id in reviewer_outtimer:
                tasks_table.update({"reviewer_id": clear_id},
                                   {"$set": {"task_list": []}}, upsert=False, multi=True)
    wait_dispatch_table.update({}, {"$addToSet": {"apply_ids": {"$each": wait_list}}}, True)
    # [reviewer_id1:offline,reviewer_id2:offline,reviewer_id2:offline]


class DispatchTask(object):
    MAX_RETRIES = 5

    # TODO: 这是映射到旧的工作。需要更新客户端并删除此
    STATUSES = {
        'PENDING': 1,
        'STARTED': 2,
        'SUCCESS': 3,
        'FAILURE': 4,
        'REVOKED': 4
    }

    def __init__(self, job_id=None, async_result=None):
        if async_result:
            self._async_result = async_result
        else:
            self._async_result = AsyncResult(job_id, app=app)

    @property
    def id(self):
        return self._async_result.id

    @classmethod
    def add_task(cls, apply_id, queue_name, task_type='new_apply', scheduled=False, metadata={}):
        logger.info("[Manager][%s] Inserting job", apply_id)
        logger.info("[Manager] Metadata: [%s]", metadata)
        try_count = 0
        job = None

        while try_count < cls.MAX_RETRIES:
            try_count += 1

            pipe = redis_connection.pipeline()
            try:
                pipe.watch(cls._job_lock_id(apply_id))
                job_id = pipe.get(cls._job_lock_id(apply_id))
                if job_id:
                    logger.info("[Manager][%s] Found existing job: %s", apply_id)
                    job = cls(job_id=job_id)
                    print job.celery_status

                    print 'add task', job.ready()
                    if job.ready():
                        logger.info("[%s] job found is ready (%s), removing lock", apply_id, job.celery_status)
                        redis_connection.delete(DispatchTask._job_lock_id(apply_id))
                        return job
                if not job:
                    pipe.multi()
                    result = execute_dispatch.apply_async(args=([apply_id], task_type, metadata), queue=queue_name)
                    job = cls(async_result=result)
                    logger.info("[Manager][%s] Created new job: %s", apply_id, job.id)
                    pipe.set(cls._job_lock_id(apply_id), job.id, settings.JOB_EXPIRY_TIME)
                    pipe.execute()
                break

            except redis.WatchError:
                continue

        if not job:
            logger.error("[Manager][%s] Failed adding job for query.", apply_id)
        return job

    def to_dict(self):
        updated_at = 0
        if self._async_result:
            if self._async_result.status == 'STARTED':
                updated_at = self._async_result.result.get('start_time', 0)

        if self._async_result.failed() and isinstance(self._async_result.result, Exception):
            error = self._async_result.result.message
        elif self._async_result.status == 'REVOKED':
            error = 'Dispatch execution cancelled.'
        else:
            error = ''

        if self._async_result.successful():
            dispatch_result_data = self._async_result.result
        else:
            dispatch_result_data = None

        return {
            'id': self._async_result.id,
            'updated_at': str(updated_at),
            'status': self.STATUSES[self._async_result.status],
            'error': error,
            'dispatch_result_data': dispatch_result_data,
        }

    @property
    def is_cancelled(self):
        return self._async_result.status == 'REVOKED'

    @property
    def celery_status(self):
        return self._async_result.status

    def ready(self):
        return self._async_result.ready()

    def cancel(self):
        return self._async_result.revoke(terminate=True, signal='SIGINT')

    @staticmethod
    def _job_lock_id(apply_id):
        return "dispatch_hash_job:%s" % apply_id

if __name__ == "__main__":

    # print ta.id
    # print ta.to_dict()
    # res = DispatchTask.add_task(11, queue_name='test', metadata={'type': '0'})
    # print res.to_dict()
    # job_id = res._job_lock_id(11)
    # print 'old job',job_id
    job_id = DispatchTask._job_lock_id([111])
    job = redis_connection.get(job_id)
    print 'job_od', job

    if not job:
        ta = DispatchTask.add_task(111, task_type='new_apply', queue_name='dispatch', metadata={'type': '0'})
        time.sleep(1)
        print redis_connection.ttl(job_id)
        print ta.ready()
        print 'res', ta.to_dict()
        print ta.celery_status
    else:
        # res = DispatchTask.add_task(11, queue_name='test', metadata={'type': '0'})
        # print res.id
        # job = redis_connection.get('986dd5b8-31cd-433b-8985-bbb2f8824cb4')
        # for i in mongo_collection['task_results'].find():
        #     print i
        print 'dddd', job
        ta = DispatchTask(job)
        print ta.to_dict()
        print ta.celery_status



