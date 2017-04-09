# -*- coding: utf-8 -*-
from random import randint
import sys
import os
sys.path.insert(0, os.getcwd())
from celery import Celery
from datetime import timedelta
from celery.schedules import crontab
import business_manager.settings as settings


app = Celery('dispatch.tasks',
             broker=settings.CELERY_BROKER,
             include=['dispatch.tasks'])


celery_schedule = {
    # 'init_dayTable': {
    #     'task': 'risk_server.tasks.init_dayTable',
    #     'schedule': crontab(minute=randint(0, 59), hour=23)
    # },
    'refresh_tasks': {
        'task': 'dispatch.tasks.refresh_tasks',
        'schedule': timedelta(minutes=settings.CRON_TIME)
    },
}

app.conf.update(CELERY_RESULT_BACKEND=settings.CELERY_BACKEND,
                CELERY_REDIS_DB='1',
                CELERY_RESULT_DB_SHORT_LIVED_SESSIONS = True,
                CELERY_REDIS_PORT='6379',
                CELERY_REDIS_HOST='127.0.0.1',
                CELERY_REDIS_PASSWORD='',
                CELERYBEAT_SCHEDULE=celery_schedule,
                BROKER_TRANSPORT_HOST="127.0.0.1",
                CELERY_TIMEZONE='UTC',
                CELERY_RESULT_SERIALIZER='json')
